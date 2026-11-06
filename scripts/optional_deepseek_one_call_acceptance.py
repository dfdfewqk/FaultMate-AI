"""One-shot OPTIONAL live DeepSeek acceptance, disabled unless TRIPLE armed.

Default invocation is STRICTLY OFFLINE and does not even read API key text.
It reports local endpoint/model/consent contract only; no outbound HTTP.

A real paid request requires ALL:
  * explicit --one-paid-request command-line switch
  * explicit --confirm-public-demo-evidence switch
  * locally set FAULTMATE_LIVE_TEST_APPROVED=YES_ONE_PAID_REQUEST
  * locally set DEEPSEEK_API_KEY (never pass/commit/paste the key)

The case is a fixed PUBLIC EXAMPLE from the existing rule-based catalog.
There is never automatic retry, background polling, stored evidence, or an
attempt to assert a final field fault diagnosis. User must understand
provider billing and foreign API transmission before arming this workflow.

This script is not run with live flags by GitHub Actions.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from faultmate.diagnostics.engine import TriageRequest
from faultmate.integration import agent
from faultmate.integration.context import ContextPreviewRequest, evidence_preview

EXPECTED_ENDPOINT = "https://api.deepseek.com/chat/completions"
EXPECTED_MODEL = "deepseek-flash"
LIVE_ARM_ENV = "FAULTMATE_LIVE_TEST_APPROVED"
LIVE_ARM_VALUE = "YES_ONE_PAID_REQUEST"
PUBLIC_DEMO_CASE_ID = "CONV-001"


def local_review_status() -> dict:
    """No provider requests, no key reads, no credential exposure."""
    payload = TriageRequest(case_id=PUBLIC_DEMO_CASE_ID, emergency_hazard="no")
    preview = evidence_preview(ContextPreviewRequest(triage=payload))
    if (preview.get("state") != "candidate_review"
        or preview.get("allowed_for_agent_reasoning") is not True
        or not isinstance(preview.get("context_sha256"), str)
        or len(preview["context_sha256"]) != 64
        or agent.ENDPOINT != EXPECTED_ENDPOINT
        or agent.MODEL != EXPECTED_MODEL
        or agent.MAX_COMPLETION_TOKENS != 600):
        raise RuntimeError("local_demo_or_provider_contract_unexpected")
    return {
        "mode": "offline_preflight_only",
        "provider_target": EXPECTED_ENDPOINT,
        "api_model": EXPECTED_MODEL,
        "max_generated_tokens": agent.MAX_COMPLETION_TOKENS,
        "public_example_case_id": PUBLIC_DEMO_CASE_ID,
        "public_evidence_preview_valid": True,
        "sensitive_user_case_transmitted": False,
        "api_key_read_or_printed": False,
        "paid_request_attempted": False,
        "model_production_approved": False,
        "live_test_requires_explicit_user_approval_and_local_key": True,
        "real_deepseek_connectivity_confirmed": False,
        "user_action_needed_now": False,
    }


def optional_one_live_paid_request(*, one_paid_request: bool,
                                   confirm_public_demo_evidence: bool) -> dict:
    """Immediately fail closed unless the user actively arms ALL controls."""
    offline = local_review_status()
    if not one_paid_request:
        if confirm_public_demo_evidence:
            raise ValueError("live_request_switch_missing")
        return offline
    if not confirm_public_demo_evidence:
        raise ValueError("explicit_public_evidence_transmission_consent_missing")
    if os.environ.get(LIVE_ARM_ENV, "") != LIVE_ARM_VALUE:
        raise ValueError("user_local_paid_request_arming_missing")
    # Do not print, persist, hash, or send the API key anywhere except the
    # existing outbound HTTPS Bearer header in the actual provider transport.
    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        raise ValueError("deepseek_api_key_missing_on_user_machine")
    triage = TriageRequest(case_id=PUBLIC_DEMO_CASE_ID, emergency_hazard="no")
    preview = evidence_preview(ContextPreviewRequest(triage=triage))
    # The preview is computed locally from one PUBLIC DEMO catalogue case.
    # Existing agent.review will enforce the exact canonical SHA and consent
    # before at most one provider call; it has NO retry on timeout/402/429/5xx.
    result = agent.review(agent.AgentReviewRequest(
        triage=triage, consent=True,
        context_sha256=preview["context_sha256"],
    ))
    # Return ONLY reviewed metadata, never the provider answer, user text,
    # paid credential, prompt, or any reflected upstream diagnostic.
    return {
        "mode": "user_explicitly_armed_one_real_paid_request",
        "provider_target": EXPECTED_ENDPOINT,
        "api_model": EXPECTED_MODEL,
        "public_example_case_id": PUBLIC_DEMO_CASE_ID,
        "paid_request_attempted": result.get("external_transfer_attempted") is True,
        "provider_response_reviewed": result.get("status") == "reviewed",
        "external_transfer_performed": result.get("external_transfer_performed"),
        "provider_status": result.get("status"),
        "safe_nonsecret_error_code": result.get("error_code"),
        "field_fault_confirmed": False,
        "safe_to_operate_equipment": False,
        "experimental_ml_model_approved": False,
        "money_spent_may_be_nonzero": result.get("external_transfer_attempted") is True,
        "no_automatic_paid_retry": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--one-paid-request", action="store_true",
                        help="Makes exactly one possible paid HTTPS request; NEVER default.")
    parser.add_argument("--confirm-public-demo-evidence", action="store_true",
                        help="Consent to send only one fixed public demo case to DeepSeek.")
    args = parser.parse_args(argv)
    try:
        result = optional_one_live_paid_request(
            one_paid_request=args.one_paid_request,
            confirm_public_demo_evidence=args.confirm_public_demo_evidence,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("mode") == "offline_preflight_only" or result.get("provider_response_reviewed") else 3
    except (RuntimeError, ValueError, KeyError, TypeError) as error:
        # Error messages here are strictly local allowlisted validation codes.
        print("DEEPSEEK_LIVE_ACCEPTANCE_BLOCKED:", str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
