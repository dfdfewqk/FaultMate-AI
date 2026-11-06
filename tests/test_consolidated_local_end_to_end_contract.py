"""Consolidated existing-app local acceptance smoke; NO paid provider or new ML.

Unlike isolated API tests, this exercises the entire unchanged request path
in ONE TestClient session: UI -> knowledge/rules -> exact preview -> agent
consent gate -> unavailable production CSV ML -> research-RAR safety guards.
No model training, physical dataset, provider key usage or EXE creation.
"""
import json

from fastapi.testclient import TestClient
import pytest

from faultmate.app import app
from faultmate.integration import agent


def test_existing_five_capability_paths_stay_coherent_and_fail_closed(monkeypatch):
    # The mock key ensures that a regression accidentally bypassing consent
    # would reach the injected tripwire, never a live paid HTTP service.
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SYNTHETIC_NO_NETWORK_BILLING_KEY")
    monkeypatch.setattr(agent, "_invoke_deepseek", lambda *_: pytest.fail(
        "consolidation review must not send paid provider request"))
    triage = {
        "equipment": "컨베이어", "case_id": "CONV-001",
        "emergency_hazard": "no",
        "observations": {"visible_jam": "yes"},
        "symptom_text": "SENSITIVE_ONLY_LOCAL_SYMPTOM_TEXT",
        "model_name": "PRIVATE_MACHINE_CODE",
    }
    with TestClient(app) as client:
        status = client.get("/api/status")
        assert status.status_code == 200
        assert status.json()["app"] == "FaultMate AI"
        html = client.get("/")
        js = client.get("/assets/app.js")
        assert html.status_code == 200 and js.status_code == 200
        assert 'id="raw-rar-upload"' in html.text
        assert "experimental-original-rar" in js.text

        cases = client.get("/api/diagnostics/options").json()["cases"]
        assert len(cases) == 7
        local = client.post("/api/diagnostics/evaluate", json=triage)
        assert local.status_code == 200
        assert local.json()["state"] == "candidate_review"
        assert local.json()["confirmed_fault"] is False
        assert local.json()["safe_to_work"] is False
        preview = client.post(
            "/api/integration/evidence-preview", json={"triage": triage})
        assert preview.status_code == 200
        p = preview.json()
        assert p["state"] == "candidate_review"
        assert len(p["context_sha256"]) == 64
        assert "SENSITIVE_ONLY_LOCAL_SYMPTOM_TEXT" not in json.dumps(p)
        assert "PRIVATE_MACHINE_CODE" not in json.dumps(p)

        for consent, digest, expected in (
            (False, p["context_sha256"], "consent_required"),
            (True, "f" * 64, "preview_mismatch"),
        ):
            response = client.post("/api/agent/review", json={
                "triage": triage,
                "consent": consent, "context_sha256": digest,
            })
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == expected
            assert result["external_transfer_attempted"] is False
            assert result["confirmed_fault"] is False
            assert result["safe_to_work"] is False

        csv = (
            b"asset_id,trial_id,source_id,vibration_rms_m_s2,"
            b"vibration_peak_m_s2,current_rms_a\n"
            b"K001,trial1,paderborn-bearing-datacenter,1.0,2.0,0.5\n"
        )
        ml = client.post("/api/ml/inspect", content=csv,
                         headers={"content-type": "text/csv"})
        assert ml.status_code == 200
        assert ml.json()["status"] == "unavailable"
        assert ml.json()["inference_performed"] is False

        # Correct bearing header must NOT override 100MB original source
        # requirement. A synthetic short body is refused BEFORE model scoring.
        rar = client.post("/api/ml/experimental-original-rar",
                          content=b"SYNTHETIC_TINY_NOT_ORIGINAL",
                          headers={
                              "content-type": "application/octet-stream",
                              "x-faultmate-bearing-id": "K001",
                          })
        assert rar.status_code == 422
        assert rar.json()["detail"] == "original_rar_source_size_invalid"

        hazard = {**triage, "emergency_hazard": "yes"}
        hold = client.post("/api/diagnostics/evaluate", json=hazard)
        assert hold.status_code == 200
        assert hold.json()["state"] == "safety_hold"
        assert hold.json()["safe_to_work"] is False
        ai = client.post("/api/agent/review", json={
            "triage": hazard, "consent": True,
            "context_sha256": p["context_sha256"],
        })
        assert ai.status_code == 200
        assert ai.json()["status"] == "blocked"
        assert ai.json()["external_transfer_attempted"] is False
