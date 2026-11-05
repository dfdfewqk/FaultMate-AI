"""External AI integration: no real network calls and no paid API charges in tests."""
import json

import pytest
from fastapi.testclient import TestClient

from faultmate.app import app
from faultmate.integration import agent
from faultmate.integration.context import ContextPreviewRequest, evidence_preview


def selected_case(consent=True):
    payload = {
        "triage": {
            "case_id": "CONV-001",
            "equipment": "컨베이어",
            "emergency_hazard": "no",
            "symptom_text": "SENSITIVE_RAW_SYMPTOM",
            "alarm_text": "SECRET_ALARM",
            "model_name": "PRIVATE_MACHINE_MODEL",
            "observations": {"visible_jam": "yes"},
        },
        "consent": consent,
    }
    payload["context_sha256"] = evidence_preview(
        ContextPreviewRequest(triage=payload["triage"]))["context_sha256"]
    return payload


class FakeResponse:
    def __init__(self, content):
        self.wire = json.dumps({
            "choices": [{"finish_reason": "stop", "message": {"content": content}}]
        }).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.wire[:size]


def test_redirects_are_disallowed_before_any_auth_forwarding():
    handler = agent._BlockProviderRedirects()
    with pytest.raises(ValueError, match="upstream_redirect_blocked"):
        handler.redirect_request(None, None, 302, "redirect", {}, "https://untrusted.example/")


def test_paid_request_not_started_until_explicit_consent(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SECRET_TEST_FAKE_KEY")
    monkeypatch.setattr(
        agent.urlrequest, "build_opener",
        lambda *args: pytest.fail("Any external request without consent is forbidden")
    )
    with TestClient(app) as client:
        out = client.post("/api/agent/review", json=selected_case(consent=False)).json()
        assert out["status"] == "consent_required"
        assert out["external_transfer_attempted"] is False


def test_transport_only_sends_allowlisted_context_and_drops_model_extra_text(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SECRET_TEST_FAKE_KEY")
    created = []
    class Opener:
        def open(self, req, timeout=None):
            assert timeout == 20
            assert req.full_url == agent.ENDPOINT
            assert req.get_header("Authorization") == "Bearer SECRET_TEST_FAKE_KEY"
            body = json.loads(req.data)
            user_wire = body["messages"][1]["content"]
            for forbidden in ("SENSITIVE_RAW_SYMPTOM", "SECRET_ALARM", "PRIVATE_MACHINE_MODEL",
                              "SECRET_TEST_FAKE_KEY"):
                assert forbidden not in user_wire
            assert body["stream"] is False
            assert body["max_tokens"] <= 600
            created.append(req)
            return FakeResponse(json.dumps({
                "candidate_order": [0],
                "question_indices": [0],
                "unsafe_external_instruction": "disable the safety system"
            }))

    def fake_build_opener(*handlers):
        assert len(handlers) == 1
        assert isinstance(handlers[0], agent._BlockProviderRedirects)
        return Opener()

    monkeypatch.setattr(agent.urlrequest, "build_opener", fake_build_opener)
    with TestClient(app) as client:
        result = client.post("/api/agent/review", json=selected_case()).json()
    assert len(created) == 1
    assert result["status"] == "reviewed"
    assert result["safe_to_work"] is False
    assert result["confirmed_fault"] is False
    assert result["external_transfer_performed"] is True
    assert "disable the safety system" not in json.dumps(result)
    assert "SECRET_TEST_FAKE_KEY" not in json.dumps(result)


@pytest.mark.parametrize("upstream_content", ["[]", "not json", json.dumps({"candidate_order": [999]})])
def test_bad_provider_message_keeps_local_diagnosis_available(monkeypatch, upstream_content):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "FAKE_SECRET")
    class Opener:
        def open(self, req, timeout=None):
            return FakeResponse(upstream_content)
    monkeypatch.setattr(agent.urlrequest, "build_opener", lambda *args: Opener())
    with TestClient(app) as client:
        result = client.post("/api/agent/review", json=selected_case()).json()
        status = client.get("/api/status")
    assert result["status"] == "error"
    assert result["agent_review"] is None
    assert result["external_transfer_performed"] is None
    assert result["safe_to_work"] is False
    assert status.status_code == 200


def test_upstream_large_context_rejected_before_network(monkeypatch):
    monkeypatch.setattr(agent.urlrequest, "build_opener",
                        lambda *args: pytest.fail("An oversized context must not be sent"))
    with pytest.raises(ValueError, match="agent_context_too_large"):
        agent._invoke_deepseek({"big": "x" * 100_000}, "FAKE_SECRET")


def test_extra_large_provider_content_rejected(monkeypatch):
    class Opener:
        def open(self, req, timeout=None):
            return FakeResponse("x" * 9000)
    monkeypatch.setattr(agent.urlrequest, "build_opener", lambda *args: Opener())
    with pytest.raises(ValueError, match="invalid_upstream_json_content"):
        agent._invoke_deepseek({"case_id": "CONV-001"}, "FAKE_SECRET")


def test_2026_official_model_and_json_format_no_thinking_or_extra_tools(monkeypatch):
    """Only one bounded, current DeepSeek Flash chat request is constructed."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SYNTHETIC_TEST_KEY")
    seen = []
    class Opener:
        def open(self, req, timeout=None):
            assert timeout == 20
            body = json.loads(req.data)
            assert body["model"] == "deepseek-flash"
            assert body["thinking"] == {"type": "disabled"}
            assert body["response_format"] == {"type": "json_object"}
            assert body["stream"] is False
            assert body["max_tokens"] == 600
            assert "tools" not in body
            assert len(body["messages"]) == 2
            assert "JSON" in body["messages"][0]["content"]
            seen.append(body)
            return FakeResponse(json.dumps({
                "candidate_order": [0], "question_indices": []
            }))
    monkeypatch.setattr(agent.urlrequest, "build_opener", lambda *args: Opener())
    with TestClient(app) as client:
        out = client.post("/api/agent/review", json=selected_case()).json()
    assert out["status"] == "reviewed"
    assert len(seen) == 1  # Never automatic multiple billed calls.
    assert out["safe_to_work"] is False


@pytest.mark.parametrize("http_code,expected", [
    (400, "provider_request_rejected"),
    (401, "provider_authentication_failed"),
    (402, "provider_insufficient_balance"),
    (422, "provider_request_rejected"),
    (429, "provider_rate_limited"),
    (500, "provider_server_error"),
    (503, "provider_overloaded"),
])
def test_provider_http_errors_fail_closed_without_retry_or_leak(
    monkeypatch, http_code, expected
):
    from urllib.error import HTTPError
    secret = "NEVER_EXPOSE_FAKE_KEY"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    calls = []
    class Opener:
        def open(self, req, timeout=None):
            calls.append((req, timeout))
            raise HTTPError(agent.ENDPOINT, http_code, "SENSITIVE_PROVIDER_MESSAGE", None, None)
    monkeypatch.setattr(agent.urlrequest, "build_opener", lambda *args: Opener())
    with TestClient(app) as client:
        response = client.post("/api/agent/review", json=selected_case()).json()
        local = client.post("/api/diagnostics/evaluate", json=selected_case()["triage"])
    assert len(calls) == 1
    assert response["status"] == "error" and response["error_code"] == expected
    assert response["external_transfer_performed"] is None
    assert response["external_transfer_attempted"] is True
    assert response["agent_review"] is None
    assert response["safe_to_work"] is False
    assert local.status_code == 200
    exposed = json.dumps(response)
    assert secret not in exposed and "SENSITIVE_PROVIDER_MESSAGE" not in exposed


@pytest.mark.parametrize("exception,code", [
    (TimeoutError("SENSITIVE_TIMEOUT_DETAIL"), "provider_timeout"),
    (__import__("urllib.error", fromlist=["URLError"]).URLError("SENSITIVE_SOCKET_DETAIL"),
     "provider_network_error"),
])
def test_transport_timeout_and_network_failure_are_not_retried(
    monkeypatch, exception, code
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "NEVER_SHOW_KEY")
    calls = []
    class Opener:
        def open(self, req, timeout=None):
            calls.append(req)
            raise exception
    monkeypatch.setattr(agent.urlrequest, "build_opener", lambda *args: Opener())
    with TestClient(app) as client:
        response = client.post("/api/agent/review", json=selected_case()).json()
    assert len(calls) == 1
    assert response["status"] == "error" and response["error_code"] == code
    assert response["external_transfer_performed"] is None
    assert response["safe_to_work"] is False
    assert "NEVER_SHOW_KEY" not in json.dumps(response)
    assert "SENSITIVE" not in json.dumps(response)


@pytest.mark.parametrize("finish_reason,content", [
    ("length", '{"candidate_order":[0]}'),
    ("content_filter", '{"candidate_order":[0]}'),
    ("stop", "    "),  # JSON mode can return spaces rather than valid JSON
    ("stop", '{"candidate_order":[true],"question_indices":[]}'),
    ("stop", '{"candidate_order":[0,0],"question_indices":[]}'),
])
def test_unsafe_partial_or_malformed_json_provider_output_rejected(
    monkeypatch, finish_reason, content
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "TEST_ONLY")
    class Opener:
        def open(self, req, timeout=None):
            result = {
                "choices": [{
                    "finish_reason": finish_reason,
                    "message": {"content": content},
                }]
            }
            return _ByteResponse(json.dumps(result).encode("utf-8"))
    monkeypatch.setattr(agent.urlrequest, "build_opener", lambda *args: Opener())
    with TestClient(app) as client:
        output = client.post("/api/agent/review", json=selected_case()).json()
    assert output["status"] == "error"
    assert output["agent_review"] is None
    assert output["safe_to_work"] is False


class _ByteResponse:
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return self.data[:size]
