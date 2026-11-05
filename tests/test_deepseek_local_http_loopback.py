"""Real LOCAL HTTP wire test of the existing DeepSeek opt-in transport.

No DNS to api.deepseek.com, no DeepSeek token, no billing, no external calls.
A local 127.0.0.1 provider stub receives actual urllib POST bytes. This is a
strict transport/integration test, NOT proof of live DeepSeek API connectivity.
"""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from faultmate.app import app
from faultmate.integration import agent
from faultmate.integration.context import ContextPreviewRequest, evidence_preview, agent_context_wire


class _LocalProvider(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        size = int(self.headers.get("content-length", "0"))
        if size > 128 * 1024 or size <= 0:
            self.send_error(413)
            return
        raw = self.rfile.read(size)
        self.server.observed.append({
            "path": self.path, "headers": dict(self.headers.items()), "body": raw,
        })
        reply = self.server.reply
        status = int(reply.get("status", 200))
        headers = dict(reply.get("headers", {}))
        body = reply.get("body")
        if body is None:
            content = json.dumps({
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": json.dumps({
                        "candidate_order": [0], "question_indices": [0],
                        "unsafe_extra": "IGNORED_NOT_LOCAL_EVIDENCE",
                    })}
                }]
            }).encode("utf-8")
        elif isinstance(body, str):
            content = body.encode("utf-8")
        else:
            content = body
        self.send_response(status)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Content-Type", "application/json")
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *_args):
        pass


@contextmanager
def local_provider(reply=None):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _LocalProvider)
    server.reply = reply or {}
    server.observed = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}/chat/completions"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.fixture
def fake_paid_key(monkeypatch):
    # Tests never know or read any actual paid DeepSeek key.
    key = "SYNTHETIC_LOCAL_LOOPBACK_NOT_A_PAID_KEY"
    monkeypatch.setenv("DEEPSEEK_API_KEY", key)
    return key


def case_payload(*, consent=True, sha=None, changed=False):
    triage = {
        "case_id": "CONV-001",
        "equipment": "컨베이어",
        "emergency_hazard": "no",
        "observations": {"visible_jam": "no" if changed else "yes"},
        "symptom_text": "SENSITIVE_SYMPTOM_NEVER_SEND",
        "alarm_text": "PRIVATE_ALARM_NEVER_SEND",
        "model_name": "PRIVATE_EQUIPMENT_ID_NEVER_SEND",
    }
    if sha is None and not changed:
        sha = evidence_preview(ContextPreviewRequest(triage=triage))["context_sha256"]
    return {"triage": triage, "consent": consent, "context_sha256": sha}


def _post(payload):
    with TestClient(app) as client:
        response = client.post("/api/agent/review", json=payload)
        assert response.status_code == 200, response.text
        return response.json()


def test_real_loopback_http_success_only_after_preview_specific_consent(fake_paid_key, monkeypatch):
    with local_provider() as (provider, endpoint):
        assert endpoint.startswith("http://127.0.0.1:")
        monkeypatch.setattr(agent, "ENDPOINT", endpoint)
        denied = _post(case_payload(consent=False))
        assert denied["status"] == "consent_required"
        assert denied["external_transfer_attempted"] is False
        assert not provider.observed

        mismatched = _post(case_payload(changed=True, sha="f" * 64))
        assert mismatched["status"] == "preview_mismatch"
        assert mismatched["external_transfer_attempted"] is False
        assert not provider.observed

        allowed = case_payload()
        preview = evidence_preview(ContextPreviewRequest(triage=allowed["triage"]))
        assert allowed["context_sha256"] == preview["context_sha256"]
        reviewed = _post(allowed)
        assert reviewed["status"] == "reviewed"
        assert reviewed["external_transfer_performed"] is True
        assert reviewed["external_transfer_attempted"] is True
        assert reviewed["safe_to_work"] is False
        assert reviewed["confirmed_fault"] is False
        assert reviewed["agent_review"]["not_confirmed"] is True
        assert len(provider.observed) == 1

        request = provider.observed[0]
        headers = {k.lower(): v for k, v in request["headers"].items()}
        assert request["path"] == "/chat/completions"
        assert headers["authorization"] == "Bearer " + fake_paid_key
        assert headers["content-type"] == "application/json"
        packet = json.loads(request["body"])
        assert packet["model"] == "deepseek-flash"
        assert packet["thinking"] == {"type": "disabled"}
        assert packet["response_format"] == {"type": "json_object"}
        assert packet["stream"] is False
        assert packet["max_tokens"] == 600
        assert len(packet["messages"]) == 2
        assert "tools" not in packet
        context_text = packet["messages"][1]["content"]
        assert context_text.endswith(agent_context_wire(preview["context"]))
        for sensitive in (
            "SENSITIVE_SYMPTOM_NEVER_SEND", "PRIVATE_ALARM_NEVER_SEND",
            "PRIVATE_EQUIPMENT_ID_NEVER_SEND", fake_paid_key
        ):
            assert sensitive not in request["body"].decode("utf-8")
            assert sensitive not in json.dumps(reviewed)
        assert "IGNORED_NOT_LOCAL_EVIDENCE" not in json.dumps(reviewed)


@pytest.mark.parametrize("status,expected", [
    (400, "provider_request_rejected"),
    (401, "provider_authentication_failed"),
    (402, "provider_insufficient_balance"),
    (429, "provider_rate_limited"),
    (500, "provider_server_error"),
    (503, "provider_overloaded"),
])
def test_real_local_http_provider_error_one_attempt_no_secret_leak(
    fake_paid_key, monkeypatch, status, expected
):
    with local_provider({
        "status": status,
        "body": json.dumps({"error": "SENSITIVE_PROVIDER_KEY_OR_USER_DATA"}),
    }) as (server, endpoint):
        monkeypatch.setattr(agent, "ENDPOINT", endpoint)
        response = _post(case_payload())
        assert len(server.observed) == 1  # NEVER auto retry a potentially billed call
        assert response["status"] == "error"
        assert response["error_code"] == expected
        assert response["external_transfer_attempted"] is True
        assert response["external_transfer_performed"] is None
        assert response["agent_review"] is None
        assert response["safe_to_work"] is False
        assert response["confirmed_fault"] is False
        assert "SENSITIVE_PROVIDER_KEY_OR_USER_DATA" not in json.dumps(response)
        assert fake_paid_key not in json.dumps(response)


def test_real_local_http_302_never_forwards_bearer_to_redirect(
    fake_paid_key, monkeypatch
):
    with local_provider() as (other_host, other_url):
        with local_provider({
            "status": 302,
            "headers": {"Location": other_url},
            "body": "",
        }) as (first, endpoint):
            monkeypatch.setattr(agent, "ENDPOINT", endpoint)
            response = _post(case_payload())
            assert len(first.observed) == 1
            assert len(other_host.observed) == 0
            assert response["status"] == "error"
            assert response["external_transfer_performed"] is None
            assert response["external_transfer_attempted"] is True
            assert fake_paid_key not in json.dumps(response)


@pytest.mark.parametrize("reply,reason", [
    ({"body": json.dumps({
        "choices": [{"finish_reason": "stop", "message": {"content": "     "}}]
    })}, "blank_json_output"),
    ({"body": json.dumps({
        "choices": [{"finish_reason": "length", "message": {
            "content": '{"candidate_order":[0],"question_indices":[]}'}}]
    })}, "partial_completion"),
    ({"body": b"z" * (128 * 1024 + 2)}, "oversized_body"),
])
def test_real_http_invalid_response_keeps_local_diagnosis_safe(
    fake_paid_key, monkeypatch, reply, reason
):
    with local_provider(reply) as (server, endpoint):
        monkeypatch.setattr(agent, "ENDPOINT", endpoint)
        r = _post(case_payload())
        assert len(server.observed) == 1, reason
        assert r["status"] == "error"
        assert r["agent_review"] is None
        assert r["external_transfer_attempted"] is True
        assert r["external_transfer_performed"] is None
        assert r["safe_to_work"] is False
        assert r["confirmed_fault"] is False


def test_fake_key_never_sends_over_network_without_verified_preview(
    fake_paid_key, monkeypatch
):
    with local_provider() as (server, endpoint):
        monkeypatch.setattr(agent, "ENDPOINT", endpoint)
        p = case_payload()
        missing = {**p, "context_sha256": None}
        denied = _post(missing)
        assert denied["status"] == "preview_mismatch"
        assert server.observed == []
        hazard = {**p, "triage": {**p["triage"], "emergency_hazard": "yes"}}
        blocked = _post(hazard)
        assert blocked["state"] == "safety_hold"
        assert blocked["status"] == "blocked"
        assert blocked["external_transfer_attempted"] is False
        assert server.observed == []
