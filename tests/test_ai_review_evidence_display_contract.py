"""AI results must preserve ALL verified local candidate evidence and safety gates.

A paid AI only selects indices. Local source context is used for all text; no
LLM-generated diagnosis, new source, or user secret may be returned.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from faultmate.app import app
from faultmate.integration import agent
from faultmate.integration.context import ContextPreviewRequest, evidence_preview


def _payload():
    triage = {
        "case_id": "CONV-001", "equipment": "컨베이어",
        "symptom_text": "RAW_PRIVATE_SYMPTOM_DO_NOT_RETURN",
        "model_name": "PRIVATE_EQUIPMENT_DO_NOT_RETURN",
        "alarm_text": "PRIVATE_ALARM_DO_NOT_RETURN",
        "observations": {"visible_jam": "yes"},
        "emergency_hazard": "no",
    }
    preview = evidence_preview(ContextPreviewRequest(triage=triage))
    assert preview["state"] == "candidate_review"
    assert len(preview["context"]["candidate_causes"]) >= 2
    return {"triage": triage, "consent": True,
            "context_sha256": preview["context_sha256"]}, preview


@pytest.mark.parametrize("ai_indices,question_indices", [
    ([0], [0]),
    ([2, 0], []),
])
def test_ai_selected_subset_does_not_hide_unselected_causes_or_questions(
        monkeypatch, ai_indices, question_indices):
    payload, preview = _payload()
    context = preview["context"]
    secret = "SYNTHETIC_PAID_KEY_NEVER_EXPOSE"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    calls = []

    def fake_response(evidence, key):
        assert key == secret
        assert evidence == context
        calls.append((evidence, key))
        return {
            "candidate_order": ai_indices,
            "question_indices": question_indices,
            "invented_instructions": "UNSAFE_FAKE_ACTION_NEVER_SHOW",
            "confirmed_fault": True,
            "safe_to_work": True,
            "sources": ["FORGED_SOURCE_NEVER_SHOW"],
        }

    monkeypatch.setattr(agent, "_invoke_deepseek", fake_response)
    with TestClient(app) as client:
        result = client.post("/api/agent/review", json=payload)
    assert result.status_code == 200
    response = result.json()
    assert len(calls) == 1
    assert response["status"] == "reviewed"
    assert response["confirmed_fault"] is False
    assert response["safe_to_work"] is False
    assert response["external_transfer_attempted"] is True
    review = response["agent_review"]
    assert review["not_confirmed"] is True
    assert review["case_id"] == context["case_id"]
    assert review["case_title"] == context["case_title"]

    all_local = context["candidate_causes"]
    kept = review["candidate_causes"] + review["other_candidate_causes"]
    assert len(kept) == len(all_local)
    assert review["candidate_causes"] == [all_local[i] for i in ai_indices]
    assert review["other_candidate_causes"] == [
        value for i, value in enumerate(all_local) if i not in ai_indices
    ]
    assert sorted(x["candidate"] for x in kept) == sorted(
        x["candidate"] for x in all_local)
    all_questions = context["missing_evidence_questions"]
    assert review["questions"] == [all_questions[i] for i in question_indices]
    assert review["other_questions"] == [
        value for i, value in enumerate(all_questions) if i not in question_indices
    ]
    assert review["pending_observations"] == context["next_questions"]
    assert review["safety_gate"] == context["required_safety_gate"]
    assert review["stop_escalation"] == context["stop_escalation"]
    assert review["limitations"] == context["limitations"]
    assert review["sources"] == context["sources"]
    declared_sources = {src["id"] for src in review["sources"]}
    assert all(set(c["source_ids"]).issubset(declared_sources) for c in kept)
    exported = json.dumps(response, ensure_ascii=False)
    for forbidden in (
        secret, payload["triage"]["symptom_text"], payload["triage"]["model_name"],
        payload["triage"]["alarm_text"], "UNSAFE_FAKE_ACTION_NEVER_SHOW",
        "FORGED_SOURCE_NEVER_SHOW",
    ):
        assert forbidden not in exported
