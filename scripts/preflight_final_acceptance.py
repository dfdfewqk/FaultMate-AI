"""Read-only final acceptance preflight for the EXISTING FaultMate AI P7.2 app.

This does not perform a DeepSeek call, load experimental model coefficients for
prediction, install anything, package an EXE or create/delete user data. It
separates automatic *current environment* checks from conditions that only
new external evidence or a user's own PC/paid API account can establish.

Run from the repository root:
    python scripts/preflight_final_acceptance.py
    python scripts/preflight_final_acceptance.py --out <NEW JSON report path>

No output file is created unless --out is explicitly given; existing output
is never overwritten. API credentials are never printed or transferred.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from faultmate.app import PROJECT_ROOT, status, integration_capabilities
from faultmate.diagnostics.engine import TriageRequest, available_options, triage
from faultmate.integration.agent import AgentReviewRequest, review
from faultmate.integration.context import ContextPreviewRequest, evidence_preview
from faultmate.integration.ml import load_validated_model, inspect_csv
from scripts.start import HOST
from scripts.audit_external_healthy_compatibility import assess_inventory
from scripts.extract_unseen_paderborn_damaged import (
    ORIGINAL_MODEL, PINNED_MODEL_SHA, canonical_json_sha256,
)

SCHEMA = "faultmate_final_readiness_preflight_v1"
EXAMPLE_CSV = (
    b"asset_id,trial_id,source_id,vibration_rms_m_s2,"
    b"vibration_peak_m_s2,current_rms_a\n"
    b"K001,T1,paderborn-bearing-datacenter,1.0,2.0,0.5\n"
)


def _check(name: str, condition: bool, detail: str) -> dict:
    return {"id": name, "passed": bool(condition), "detail": detail}


def collect_readiness() -> dict:
    """Pure read-only application checks; never request an AI review with consent."""
    checks: list[dict] = []
    sys_version_ok = sys.version_info >= (3, 10)
    checks.append(_check("python_3_10_or_later", sys_version_ok,
                         "Python 3.10+ required for existing launcher"))
    checks.append(_check("project_root_stable", PROJECT_ROOT == ROOT,
                         "Application is imported from this existing repository"))
    checks.append(_check("loopback_only", HOST == "127.0.0.1",
                         "Existing launcher binds 127.0.0.1 only"))

    web = ROOT / "web"
    files_ok = all((web / item).is_file() and (web / item).stat().st_size
                   for item in ("index.html", "app.js", "style.css"))
    checks.append(_check("existing_web_assets", files_ok,
                         "P7.2 original HTML, JS, and CSS are present"))

    current_status = status()
    checks.append(_check("existing_p72_status",
                         current_status.get("api") == "ok"
                         and current_status.get("app") == "FaultMate AI"
                         and current_status.get("ui_release") == "P7.2-Final"
                         and current_status.get("phase") == "P2",
                         "P2 is the preserved compatibility field, not the delivery stage"))

    options = available_options()
    checks.append(_check("seven_local_cases", len(options.get("cases", [])) == 7,
                         "Seven existing illustrative local cases remain available"))

    # These checks call application Python functions in-process, not localhost
    # HTTP or any external provider, and do not write anything.
    emergency = TriageRequest(case_id="CONV-001", emergency_hazard="yes")
    hazard = triage(emergency)
    emergency_preview = evidence_preview(ContextPreviewRequest(triage=emergency))
    hold = review(AgentReviewRequest(triage=emergency, consent=True))
    checks.append(_check(
        "hazard_never_sends_ai",
        hazard.get("state") == "safety_hold"
        and emergency_preview.get("context") is None
        and emergency_preview.get("context_sha256") is None
        and hold.get("status") == "blocked"
        and hold.get("external_transfer_attempted") is False
        and hold.get("safe_to_work") is False,
        "Emergency state prevents even a consent-marked AI request",
    ))

    normal = TriageRequest(case_id="CONV-001", emergency_hazard="no")
    preview = evidence_preview(ContextPreviewRequest(triage=normal))
    without_consent = review(AgentReviewRequest(
        triage=normal, consent=False,
        context_sha256=preview.get("context_sha256")))
    without_preview = review(AgentReviewRequest(triage=normal, consent=True))
    checks.append(_check(
        "ai_preview_consent_gate",
        preview.get("allowed_for_agent_reasoning") is True
        and isinstance(preview.get("context_sha256"), str)
        and len(preview["context_sha256"]) == 64
        and without_consent.get("status") == "consent_required"
        and without_consent.get("external_transfer_attempted") is False
        and without_preview.get("status") == "preview_mismatch"
        and without_preview.get("external_transfer_attempted") is False,
        "No AI request can leave without an exact preview and per-request consent",
    ))

    capabilities = integration_capabilities()
    agent = capabilities.get("agent", {})
    ml = capabilities.get("ml", {})
    checks.append(_check(
        "read_only_control_contract",
        capabilities.get("hard_limits", {}).get("remote_control") is False
        and capabilities["hard_limits"].get("bypass_interlocks") is False
        and capabilities["hard_limits"].get("automatic_restart") is False
        and agent.get("requires_explicit_per_request_consent") is True,
        "AI remains read-only; no interlocks, restarting or remote equipment control",
    ))

    approved_model = load_validated_model()
    csv_check = inspect_csv(EXAMPLE_CSV)
    ml_is_closed = (approved_model is None
                    and ml.get("inference_enabled") is False
                    and csv_check.get("status") == "unavailable"
                    and csv_check.get("inference_performed") is False
                    and csv_check.get("confirmed_fault") is False)
    checks.append(_check(
        "unreviewed_ml_not_deployed", ml_is_closed,
        "The research-only bearing model is not promoted to the SI CSV inference API",
    ))

    research_model_integrity = (
        ORIGINAL_MODEL.is_file()
        and canonical_json_sha256(ORIGINAL_MODEL) == PINNED_MODEL_SHA
    )
    checks.append(_check(
        "real_research_model_unmodified", research_model_integrity,
        "Original real-data research model SHA-256 is unchanged; never auto-load",
    ))

    readiness = assess_inventory()
    no_fresh_healthy = (
        readiness.get("no_approved_healthy_source") is True
        and readiness.get("new_healthy_bearings_validated") == 0
        and readiness.get("false_positive_rate_measured") is False
        and readiness.get("overall_accuracy_measured") is False
        and readiness.get("ml_predictions_performed") is False
        and len(readiness.get("results", [])) == 3
    )
    checks.append(_check(
        "external_healthy_evidence_honest", no_fresh_healthy,
        "Existing normal assets are reused and incompatible external metadata cannot prove specificity",
    ))

    # Deliberately do not read the contents of DEEPSEEK_API_KEY; the state
    # reveals nothing and no network call is made by this preflight.
    all_checks = all(item["passed"] for item in checks)
    return {
        "schema": SCHEMA,
        "project": "FaultMate AI",
        "ui_release": current_status.get("ui_release"),
        "scope": "offline_read_only_local_environment_preflight",
        "automatic_local_checks_passed": all_checks,
        "checks_passed_count": sum(c["passed"] for c in checks),
        "checks_count": len(checks),
        "checks": checks,
        "paid_api_requests_performed": 0,
        "external_transfer_attempted": False,
        "model_training_performed": False,
        "experimental_model_activated": False,
        "new_healthy_bearing_evaluation_performed": False,
        "release_ready": False,
        "release_gate": "BLOCKED_PENDING_EXTERNAL_VALIDATION_AND_USER_ACCEPTANCE",
        "external_dependencies": [
            "New source-verified physically independent healthy bearing recordings "
            "with compatible two-channel, four-condition measurement protocol, "
            "or a separately scoped and validated external-domain model",
            "Independent false-positive/specificity evaluation and review of KI21 damage miss",
            "Paderborn CC BY-NC 4.0 noncommercial restriction/permission if commercial",
        ],
        "only_user_can_complete": [
            "Final Windows PC double-click and normal UI acceptance using real installed environment",
            "OPTIONAL: authorize a separately billed DeepSeek live API request and provide "
            "a locally configured key; never paste the key into chat or commit",
        ],
        "not_claimed": [
            "New field accuracy or independent healthy specificity",
            "Live paid DeepSeek connectivity",
            "User's Windows PC acceptance",
            "Production-approved real bearing fault prediction",
            "EXE/ZIP distribution",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        help="Optional NEW JSON report path. Never overwrite.")
    args = parser.parse_args(argv)
    try:
        result = collect_readiness()
        text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.out is not None:
            if args.out.exists() or args.out.is_symlink():
                raise ValueError("readiness_report_exists_refuse_to_overwrite")
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as handle:
                handle.write(text)
        print(text, end="")
        # 0 means all automatic LOCAL gates pass, NOT release-ready.
        return 0 if result["automatic_local_checks_passed"] else 2
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("FAULTMATE_PREFLIGHT_FAILED_CLOSED:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
