"""Evidence-backed go/no-go for applying the real experimental bearing ML.

Current decision: REAL ML training happened; production model activation must
remain blocked. This command does not fit, score, download, call AI or write
user files. It checks the original frozen model bytes, prospective test
manifest, known healthy-source limitations and actual app inference state.

The historical damaged-only 7/8 CI result is linked but NOT silently
recomputed from eight absent experimental source JSONs in this checkout.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from faultmate.integration.ml import load_validated_model
from scripts.audit_external_healthy_compatibility import assess_inventory
from scripts.extract_unseen_paderborn_damaged import (
    MANIFEST, ORIGINAL_MODEL, PINNED_MODEL_SHA, KNOWN_NEW_MD5,
    canonical_json_sha256, verified_manifest,
)
from scripts.audit_bjtu_primary_layout import (
    PUBLISHED_LAYOUT, verify_published_layout,
)

REPORT_SCHEMA = "faultmate_frozen_bearing_ml_application_decision_v1"
DAMAGED_CI = "https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41971495239"


class ModelDecisionEvidenceError(ValueError):
    pass


def _check_frozen_model():
    if not ORIGINAL_MODEL.is_file() or canonical_json_sha256(ORIGINAL_MODEL) != PINNED_MODEL_SHA:
        raise ModelDecisionEvidenceError("frozen_model_sha256_mismatch")
    data = json.loads(ORIGINAL_MODEL.read_text(encoding="utf-8"))
    if (data.get("status") != "experimental_unapproved_not_for_runtime"
        or data.get("approved_for_runtime") is not False
        or data.get("runtime_inference_compatible") is not False
        or data.get("source_numeric_si_units_verified") is not False
        or data.get("training_asset_count") != 10
        or data.get("training_asset_ids") != [
            "K001", "K002", "K003", "K004", "K005",
            "KA04", "KA16", "KB23", "KI04", "KI16"
        ]
        or data.get("source_cohort_license") != "CC BY-NC 4.0"
        or data.get("decision_threshold_fixed") != 0.5):
        raise ModelDecisionEvidenceError("frozen_model_research_contract_changed")
    return data


def decide_model_application() -> dict:
    model = _check_frozen_model()
    preregistered = verified_manifest()
    if (preregistered.get("original_model_sha256") != PINNED_MODEL_SHA
        or len(preregistered.get("assets", [])) != 8
        or {x["id"] for x in preregistered["assets"]} != set(KNOWN_NEW_MD5)
        or any(x.get("label") != "damaged" for x in preregistered["assets"])
        or preregistered.get("historical_opened_holdout_assets") != ["K006", "KI18"]):
        raise ModelDecisionEvidenceError("unseen_damaged_test_evidence_changed")

    source_review = assess_inventory()
    verify_published_layout(json.loads(
        PUBLISHED_LAYOUT.read_text(encoding="utf-8")))
    if (source_review.get("new_healthy_bearings_validated") != 0
        or source_review.get("false_positive_rate_measured") is not False
        or source_review.get("overall_accuracy_measured") is not False
        or source_review.get("ml_predictions_performed") is not False
        or source_review.get("no_approved_healthy_source") is not True
        or len(source_review.get("results", [])) != 4
        or any(item["direct_frozen_model_prediction_allowed"]
               for item in source_review["results"])):
        raise ModelDecisionEvidenceError("healthy_source_evidence_unjustifiably_approved")

    active = load_validated_model()
    if active is not None:
        raise ModelDecisionEvidenceError("unexpected_existing_runtime_ml_activated")

    return {
        "schema": REPORT_SCHEMA,
        "review_stage": "bearing_ml_application_no_go_review_completed",
        "existing_app_can_continue_with_local_rule_based_diagnostics": True,
        "original_real_training_model_content_verified": True,
        "research_model_sha256": PINNED_MODEL_SHA,
        "training_physical_bearings": model["training_asset_count"],
        "research_only_model_not_a_production_model": True,
        "source_conditions_required": 4,
        "repeated_recordings_per_condition_required": 20,
        "source_si_unit_calibration_verified": False,
        "experimental_model_runtime_input_compatible": False,
        "historical_damaged_evaluation": {
            "previous_ci_run": DAMAGED_CI,
            "tested_new_physical_damaged_bearings": 8,
            "previous_ci_reported_detected": 7,
            "previous_ci_reported_missed": ["KI21"],
            "numbers_recomputed_in_this_command": False,
            "status": "historically_reported_from_separate_real_ci_run_not_a_new_test",
        },
        "external_source_candidates_reviewed": len(source_review["results"]),
        "new_independent_healthy_bearings_original_signals_verified": 0,
        "new_independent_healthy_specificity_measured": False,
        "normal_false_positive_rate_measured": False,
        "general_accuracy_measured": False,
        "no_claim_of_field_performance": True,
        "production_ml_activation_allowed": False,
        "standalone_research_model_auto_approval_allowed": False,
        "bearing_model_loaded_in_app": False,
        "production_model_decision": "NO_GO_MISSING_INDEPENDENT_NORMAL_EVIDENCE_AND_INPUT_CONTRACT",
        "dataset_evidence_blockers": [
            "All six original Paderborn physical healthy bearings were previously opened",
            "External KAIST datasets use different sample rates and/or operating conditions",
            "BJTU has one normal health-state folder and nine operating conditions, NOT documented nine healthy physical bearings",
            "HUST independently documents three healthy prototype bearings but vibration-only 51.2kHz and three loads; no paired motor current and not the original 6203/4-condition contract",
            "Original published BJTU split ZIP files are large; original raw/physical IDs and commercial data rights unverified",
        ],
        "source_and_product_limits": [
            "Paderborn original CC BY-NC 4.0 does not authorize commercial source use",
            "Fitted research model expects twelve unitless features aggregated over 80 sensor recordings, not the app's three SI CSV fields",
            "Raw sensor SI calibration is unverified; no engineering amplitude thresholds may be inferred",
            "Earlier unseen KI21 damaged bearing was missed; cannot tune on already opened test and call it new independent evidence",
        ],
        "next_developer_work": [
            "If verifiable new physical healthy bearings become available, register raw source hashes, identity and matched input contract BEFORE new scoring",
            "If evaluating an incompatible source, independently pre-register a NEW domain adaptation/evaluation procedure; never label it Paderborn frozen-model independent validation",
            "Continue core rule-based app and user safety regression without enabling experimental ML",
        ],
        "user_action_needed_now": False,
        "paid_deepseek_api_called": False,
        "new_ml_training_or_inference_performed": False,
        "main_or_user_data_modified": False,
        "package_created": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=False, type=Path,
                        help="Optional NEW JSON report path. Never overwrite.")
    args = parser.parse_args(argv)
    try:
        report = decide_model_application()
        output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.out is not None:
            if args.out.exists() or args.out.is_symlink():
                raise ModelDecisionEvidenceError("cannot_overwrite_prior_ml_decision")
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as f:
                f.write(output)
        print(output, end="")
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("FROZEN_MODEL_APPLICATION_DECISION_FAILED_CLOSED:", str(exc),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
