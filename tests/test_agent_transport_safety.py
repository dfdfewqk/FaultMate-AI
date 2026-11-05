"""External AI integration: no real network calls and no paid API charges in tests."""
import json

import pytest
from fastapi.testclient import TestClient

from faultmate.app import app
from faultmate.integration import agent


def selected_case(consent=True):
    return {
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
