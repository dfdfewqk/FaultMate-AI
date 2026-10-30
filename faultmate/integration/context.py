"""Produce a small, deterministic, citation-backed context preview for a future AI agent.

IMPORTANT: This module NEVER sends data to DeepSeek and never infers a fault.
The output is a *preview*; consent and external transmission must be implemented
separately by the Antigravity agent with an explicit, per-request user action.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from faultmate.diagnostics.engine import TriageRequest, triage
from faultmate.knowledge.repository import load_catalog

CONTRACT_VERSION = "1.0.0"


class ContextPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    triage: TriageRequest


def capabilities():
    return {
        "contract_version": CONTRACT_VERSION,
        "integration_status": "p6_optional_agent_backend_ml_untrained",
        "owner": {"agent": "ChatGPT_P6_backend", "ml": "ChatGPT_P6_backend"},
        "agent": {
            "connected": False,
            "external_transfer": False,
            "requires_explicit_per_request_consent": True,
            "read_only_tools": [
                "GET /api/knowledge/overview",
                "GET /api/knowledge/sources",
                "GET /api/knowledge/cases",
                "GET /api/knowledge/cases/{case_id}",
                "GET /api/diagnostics/options",
                "POST /api/diagnostics/evaluate",
                "POST /api/integration/evidence-preview",
            ],
        },
        "ml": {
            "connected": False,
            "trained": False,
            "inference_enabled": False,
            "requires_independent_validated_fault_labels": True,
        },
        "hard_limits": {
            "confirmed_fault": False,
            "safe_to_work": False,
            "remote_control": False,
            "bypass_interlocks": False,
            "automatic_restart": False,
            "unauthorized_external_transfer": False,
        },
    }


def _reference(source: dict) -> dict:
    """Explicit allowlist; never expose additional fields accidentally."""
    return {k: source[k] for k in (
        "id", "title", "organization", "url", "evidence_scope", "limit"
    )}


def evidence_preview(request: ContextPreviewRequest) -> dict:
    assessment = triage(request.triage)
    state = assessment["state"]
    result = {
        "contract_version": CONTRACT_VERSION,
        "state": state,
        "allowed_for_agent_reasoning": False,
        "external_transfer_performed": False,
        "user_consent_captured": False,
        "ml_inference_performed": False,
        "confirmed_fault": False,
        "safe_to_work": False,
        "stored": False,
        "notice": assessment["notice"],
        "context": None,
    }
    if state == "safety_hold":
        # Safety hold never includes diagnostic candidates, observed values,
        # narrative free text, or machine identifiers.
        result["message"] = assessment["message"]
        return result
    if state == "selection_required":
        # Free-text based matches are only suggestions, not a selected diagnosis.
        result["message"] = "사례를 직접 선택해야 근거 자료 미리보기를 생성할 수 있습니다."
        return result

    assert state == "candidate_review"
    known_sources = {s["id"]: s for s in load_catalog()["sources"]}
    referenced_ids = {
        source_id
        for candidate in assessment["candidate_causes"]
        for source_id in candidate["source_ids"]
    }
    if not referenced_ids.issubset(known_sources):
        # Fail closed for any corrupt or unvalidated source reference.
        raise ValueError("unknown_source_reference")

    # No raw symptom/alarm/model strings, operator names, notes, timestamps,
    # file contents, secrets, or training records are copied into preview.
    result["allowed_for_agent_reasoning"] = True
    result["context"] = {
        "case_id": assessment["case_id"],
        "equipment": assessment["equipment"],
        "case_title": assessment["case_title"],
        "case_status": "illustrative_evidence_map",
        "observations": {
            key: request.triage.observations[key]
            for key in sorted(request.triage.observations)
        },
        "self_reported_unverified": True,
        "candidate_causes": [{
            "candidate": c["candidate"],
            "why_to_consider": c["why_to_consider"],
            "source_ids": list(c["source_ids"]),
            "not_confirmed": True,
            "review_group": c["review_group"],
        } for c in assessment["candidate_causes"]],
        "missing_evidence_questions": list(assessment["additional_information_questions"]),
        "next_questions": list(assessment["next_questions"]),
        "required_safety_gate": assessment["safety_gate"],
        "stop_escalation": assessment["stop_escalation"],
        "limitations": list(assessment["limitations"]),
        "sources": [_reference(known_sources[sid]) for sid in sorted(referenced_ids)],
        "prohibited_actions": [
            "설비 제어", "인터록 우회", "무단 재기동", "고장 확정", "작업 안전 허가"
        ],
    }
    return result
