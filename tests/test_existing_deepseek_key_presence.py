"""The existing DeepSeek key is checked locally without exposing its bytes.

Presence is not a real external authentication/connection test and MUST NOT
authorize a paid request. These cases use synthetic keys and no network.
"""
import json

from fastapi.testclient import TestClient

from faultmate.app import app
from faultmate.integration import agent


def test_existing_server_key_detected_without_any_paid_request_or_key_leak(monkeypatch):
    secret = "SYNTHETIC_EXISTING_KEY_MUST_NEVER_BE_EXPOSED"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    monkeypatch.setattr(
        agent, "_invoke_deepseek",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("local key presence must never call provider")),
    )
    with TestClient(app) as client:
        status = client.get("/api/integration/capabilities")
        refreshed = client.get("/api/integration/capabilities")
        local_diagnosis = client.post("/api/diagnostics/evaluate", json={
            "case_id": "CONV-001", "equipment": "컨베이어",
            "emergency_hazard": "no",
            "observations": {"visible_jam": "yes"},
        })
    for response in (status, refreshed):
        assert response.status_code == 200
        body = response.json()
        assert body["agent"]["configured"] is True
        assert body["agent"]["connected"] is False
        assert body["agent"]["external_transfer"] is False
        assert body["ml"]["inference_enabled"] is False
        assert secret not in response.text
    assert local_diagnosis.status_code == 200
    assert local_diagnosis.json()["safe_to_work"] is False
    assert secret not in json.dumps(local_diagnosis.json())


def test_existing_key_presence_updates_when_server_environment_changes(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "SYNTHETIC_PRESENT_KEY")
        assert client.get("/api/integration/capabilities").json()["agent"]["configured"] is True
        monkeypatch.setenv("DEEPSEEK_API_KEY", "   ")
        assert client.get("/api/integration/capabilities").json()["agent"]["configured"] is False
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        assert client.get("/api/integration/capabilities").json()["agent"]["configured"] is False
