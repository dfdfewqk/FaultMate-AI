"""Real application route integration with fake provider; no external network or paid calls."""
from __future__ import annotations

import hashlib
import json

from fastapi.testclient import TestClient
import pytest

from faultmate.app import app
from faultmate.integration import agent
from faultmate.integration.context import agent_context_sha256, agent_context_wire
from faultmate.diagnostics.engine import RULES

TRIAGE = {
    "case_id": "CONV-001", "equipment": "컨베이어",
    "emergency_hazard": "no",
    "observations": {"visible_jam": "yes"},
    "symptom_text": "VERY_PRIVATE_SYMPTOM_TEXT",
    "alarm_text": "VERY_PRIVATE_ALARM",
    "model_name": "VERY_PRIVATE_MACHINE_ID",
}


def _preview(client, triage=TRIAGE):
    response = client.post("/api/integration/evidence-preview", json={"triage": triage})
    assert response.status_code == 200, response.text
    return response.json()


def test_seven_cases_still_integrate_with_local_rules_and_safe_contexts():
    with TestClient(app) as client:
        options = client.get("/api/diagnostics/options").json()
        assert {item["case_id"] for item in options["cases"]} == set(RULES)
        for case_id in RULES:
            triage = {"case_id": case_id, "emergency_hazard": "no"}
            local = client.post("/api/diagnostics/evaluate", json=triage)
            preview = _preview(client, triage)
            assert local.status_code == 200
            assert local.json()["state"] == preview["state"] == "candidate_review"
            assert preview["context_sha256"] == agent_context_sha256(preview["context"])
            assert len(preview["context_sha256"]) == 64
            assert preview["allowed_for_agent_reasoning"] is True
            assert local.json()["confirmed_fault"] is False
            assert local.json()["safe_to_work"] is False


def test_preview_digest_is_exact_outbound_transport_context(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "TEST_ONLY_NEVER_BILL")
    context_received = []
    def fake_invoke(context, key):
        assert key == "TEST_ONLY_NEVER_BILL"
        context_received.append(context)
        return {"candidate_order": [0], "question_indices": [0],
                "safe_to_work": True, "summary": "FAKE_UNSAFE_INSTRUCTION"}
    monkeypatch.setattr(agent, "_invoke_deepseek", fake_invoke)
    with TestClient(app) as client:
        local_before = client.post("/api/diagnostics/evaluate", json=TRIAGE).json()
        preview = _preview(client)
        assert "VERY_PRIVATE_" not in json.dumps(preview)
        digest = hashlib.sha256(agent_context_wire(preview["context"]).encode("utf-8")).hexdigest()
        assert preview["context_sha256"] == digest
        response = client.post("/api/agent/review", json={
            "triage": TRIAGE, "consent": True, "context_sha256": digest})
        result = response.json()
        assert response.status_code == 200
        assert result["status"] == "reviewed"
        assert result["external_transfer_performed"] is True  # simulated only
        assert result["safe_to_work"] is False and result["confirmed_fault"] is False
        assert len(context_received) == 1 and context_received[0] == preview["context"]
        assert "FAKE_UNSAFE_INSTRUCTION" not in json.dumps(result)
        assert client.post("/api/diagnostics/evaluate", json=TRIAGE).json() == local_before
        assert client.get("/api/integration/capabilities").json()["ml"]["inference_enabled"] is False


@pytest.mark.parametrize("patch", [
    {"consent": False},
    {"consent": True},  # no digest = no network
    {"consent": True, "context_sha256": "f" * 64},  # stale/fake digest
])
def test_no_paid_call_without_consent_and_exact_preview(monkeypatch, patch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "TEST_ONLY")
    monkeypatch.setattr(agent, "_invoke_deepseek",
                        lambda *_: pytest.fail("unexpected network request"))
    with TestClient(app) as client:
        response = client.post("/api/agent/review", json={"triage": TRIAGE, **patch})
    assert response.status_code == 200
    assert response.json()["status"] == (
        "consent_required" if not patch["consent"] else "preview_mismatch")
    assert response.json()["external_transfer_attempted"] is False


def test_changed_observation_after_review_requires_new_preview(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "TEST_ONLY")
    monkeypatch.setattr(agent, "_invoke_deepseek",
                        lambda *_: pytest.fail("unreviewed evidence must not leave localhost"))
    with TestClient(app) as client:
        preview = _preview(client)
        updated = {**TRIAGE, "observations": {"visible_jam": "no"}}
        result = client.post("/api/agent/review", json={
            "triage": updated, "consent": True,
            "context_sha256": preview["context_sha256"]}).json()
        assert result["status"] == "preview_mismatch"
        assert result["external_transfer_attempted"] is False
        assert _preview(client, updated)["context_sha256"] != preview["context_sha256"]


def test_safety_hold_blocks_even_previously_reviewed_context(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "TEST_ONLY")
    monkeypatch.setattr(agent, "_invoke_deepseek",
                        lambda *_: pytest.fail("safety hold must block paid calls"))
    with TestClient(app) as client:
        preview = _preview(client)
        dangerous = {**TRIAGE, "emergency_hazard": "yes"}
        blocked_preview = _preview(client, dangerous)
        assert blocked_preview["context"] is None
        assert blocked_preview["context_sha256"] is None
        result = client.post("/api/agent/review", json={
            "triage": dangerous, "consent": True,
            "context_sha256": preview["context_sha256"]}).json()
        assert result["status"] == "blocked"
        assert result["state"] == "safety_hold"
        assert result["agent_review"] is None
        assert result["external_transfer_attempted"] is False


def test_user_supplied_digest_schema_is_rejected_if_unsafe():
    with TestClient(app) as client:
        invalid = client.post("/api/agent/review", json={
            "triage": TRIAGE, "consent": True,
            "context_sha256": "not-a-hex-sha"})
        assert invalid.status_code == 422


def test_local_ml_remains_unavailable_while_no_source_calibration():
    with TestClient(app) as client:
        features = (b"asset_id,trial_id,source_id,vibration_rms_m_s2,"
                    b"vibration_peak_m_s2,current_rms_a\n"
                    b"K001,N15_M07_F10_K001_1.mat,paderborn-bearing-datacenter,1,2,0.5\n")
        r = client.post("/api/ml/inspect", content=features,
                        headers={"content-type": "text/csv"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "unavailable"
        assert data["inference_performed"] is False
        assert data["confirmed_fault"] is False
        assert data["safe_to_work"] is False
