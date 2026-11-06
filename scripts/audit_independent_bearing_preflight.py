"""Offline fail-closed independent physical-bearing preflight, NOT a model eval.

Combines existing pinned source-model and reviewed-source audits with a
DRAFT prospective source plan. Even truthful metadata cannot establish raw
signal identity, two independent physical classes or model compatibility.
This module does no downloads, re-fitting, inference, AI, file edits or
runtime activation. It never authorizes using previously opened Paderborn
test bearings as prospective samples.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_external_healthy_compatibility import assess_inventory
from scripts.evaluate_unseen_paderborn_damaged import (
    KNOWN_TRAIN, frozen_coefficients,
)
from scripts.extract_unseen_paderborn_damaged import (
    KNOWN_NEW_MD5, PREVIOUS_OPENED,
)

PLAN_PATH = ROOT / "docs" / "experiments" / (
    "INDEPENDENT_BEARING_PROSPECTIVE_PLAN_DRAFT_20261106.json")
PLAN_SCHEMA = "faultmate_prospective_independent_physical_bearing_plan_draft_v1"
EXPOSED_PADERBORN = (KNOWN_TRAIN | set(KNOWN_NEW_MD5) |
                     set(PREVIOUS_OPENED))
EXPOSED_HEALTHY = {f"K{i:03d}" for i in range(1, 7)}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class IndependentSourceGateError(ValueError):
    pass


def _inspect_proposed_assets(rows: object) -> int:
    """Metadata hygiene only. No row can certify real independent source."""
    if not isinstance(rows, list):
        raise IndependentSourceGateError("proposed_physical_asset_list_required")
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise IndependentSourceGateError("invalid_proposed_asset_metadata")
        asset = row.get("physical_asset_id")
        source = row.get("source_id")
        label = row.get("primary_label")
        sha = row.get("proposed_original_archive_sha256")
        if (not isinstance(asset, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{2,80}", asset)
            or not isinstance(source, str) or not re.fullmatch(
                r"[A-Za-z0-9_.:-]{3,120}", source)
            or label not in {"healthy", "damaged"}
            or not isinstance(sha, str) or not SHA256_RE.fullmatch(sha)):
            raise IndependentSourceGateError("invalid_proposed_asset_provenance_fields")
        # Strings are just applicant-proposed identities; no original bytes
        # were read, so even a well-shaped SHA is not a verified checksum.
        if (asset in EXPOSED_PADERBORN or asset in seen_ids
            or sha in seen_hashes):
            raise IndependentSourceGateError(
                "historical_or_duplicate_physical_asset_reuse")
        seen_ids.add(asset)
        seen_hashes.add(sha)
    return len(seen_ids)


def inspect_prospective_draft(plan: dict) -> dict:
    if not isinstance(plan, dict):
        raise IndependentSourceGateError("candidate_plan_object_required")
    model = frozen_coefficients()  # pinned original research-model SHA check
    if (plan.get("schema") != PLAN_SCHEMA
        or plan.get("status") != "draft_before_new_source_not_preregistered"
        or plan.get("frozen_research_model_sha256") != model["model_sha256"]
        or plan.get("preexisting_experiment_results_seen") is not True
        or plan.get("never_reuse_historical_bearings_as_new_test") is not True):
        raise IndependentSourceGateError("prospective_plan_cannot_rewrite_history")

    n_proposals = _inspect_proposed_assets(plan.get("physical_asset_proposals"))
    # Metadata-only proposals NEVER unlock model scoring even if they appear
    # complete; actual original file hashes, physical identities and protocol
    # have not been checked, and there is no prospective frozen acceptance.
    if plan.get("prospective_test_approved_to_run") is not False:
        raise IndependentSourceGateError("draft_cannot_claim_test_approval")
    checks = {
        "new_source_selected": isinstance(plan.get("proposed_source_id"), str)
                               and bool(plan["proposed_source_id"].strip()),
        "proposed_use_license_verified": (
            plan.get("source_license_for_proposed_use_verified") is True),
        "new_healthy_bearings_originals_verified": (
            type(plan.get("independent_physical_healthy_bearing_count_verified"))
            is int and plan["independent_physical_healthy_bearing_count_verified"] > 0),
        "new_damaged_bearings_originals_verified": (
            type(plan.get("independent_physical_damaged_bearing_count_verified"))
            is int and plan["independent_physical_damaged_bearing_count_verified"] > 0),
        "prospective_sample_size_frozen": (
            type(plan.get("planned_minimum_healthy_bearings_before_data")) is int
            and plan["planned_minimum_healthy_bearings_before_data"] > 0
            and type(plan.get("planned_minimum_damaged_bearings_before_data")) is int
            and plan["planned_minimum_damaged_bearings_before_data"] > 0),
        "bearing_level_metric_ci_and_acceptance_frozen": all(
            isinstance(plan.get(k), str) and bool(plan[k].strip())
            for k in ("primary_bearing_level_metric_frozen_before_data",
                      "confidence_interval_method_frozen_before_data",
                      "minimum_acceptable_result_frozen_before_data")),
        "matched_four_conditions_and_trials_verified": (
            plan.get("four_official_conditions_20_mat_each_bearing_verified") is True),
        "paired_original_channels_verified": (
            plan.get("paired_64000hz_vibration_and_motor_current_original_signals_verified")
            is True),
        "source_archive_signal_hashes_verified": (
            plan.get("raw_source_archive_and_signal_sha256_verified") is True),
        "physical_and_fingerprint_nonoverlap_verified": (
            plan.get("zero_reuse_of_previously_opened_physical_bearings_and_signal_hashes_verified")
            is True),
        "prospective_protocol_frozen_before_new_data": (
            plan.get("protocol_committed_prior_to_any_new_test_source") is True),
    }
    return {
        "schema": "faultmate_new_independent_bearing_preflight_v1",
        "status": "NO_GO_NO_NEW_PROSPECTIVE_PHYSICAL_BEARING_COHORT",
        "original_frozen_model_verified": True,
        "model_sha256": model["model_sha256"],
        "paderborn_all_six_healthy_previously_opened": (
            EXPOSED_HEALTHY <= EXPOSED_PADERBORN),
        "exposed_paderborn_physical_bearings_for_exclusion": len(EXPOSED_PADERBORN),
        "proposed_asset_metadata_rows": n_proposals,
        "readiness_checks": checks,
        "missing_preconditions": [name for name, ok in checks.items() if not ok],
        "draft_not_a_preregistered_study": True,
        "metadata_proposals_never_verified_raw_evidence": True,
        "new_independent_normal_bearings_verified": 0,
        "new_independent_damaged_bearings_verified": 0,
        "new_independent_specificity_or_accuracy_measured": False,
        "model_retrained_or_scored": False,
        "production_ml_activation_allowed": False,
        "paid_api_called": False,
    }


def audit_current_readiness(plan_path: Path = PLAN_PATH) -> dict:
    if not plan_path.is_file() or plan_path.is_symlink():
        raise IndependentSourceGateError("draft_plan_missing_or_symlink")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    report = inspect_prospective_draft(plan)
    source = assess_inventory()
    if (source.get("no_approved_healthy_source") is not True
        or source.get("new_healthy_bearings_validated") != 0
        or source.get("false_positive_rate_measured") is not False
        or any(r.get("direct_frozen_model_prediction_allowed") is not False
               for r in source.get("results", []))):
        raise IndependentSourceGateError("reviewed_source_evidence_unexpectedly_promoted")
    report["existing_public_candidate_sources_reviewed"] = len(source["results"])
    report["source_rejections"] = [
        {"source_id": r["source_id"],
         "reasons": r["blocking_reasons"]}
        for r in source["results"]
    ]
    report["current_source_review_unmodified"] = True
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, default=PLAN_PATH)
    p.add_argument("--out", type=Path,
                   help="Optional new JSON output path, never overwrite")
    args = p.parse_args(argv)
    try:
        report = audit_current_readiness(args.plan)
        output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.out is not None:
            if args.out.is_symlink() or args.out.exists():
                raise IndependentSourceGateError("refuse_to_overwrite_readiness_report")
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(output)
        print(output, end="")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print("PROSPECTIVE_BEARING_EVALUATION_GATE_FAIL_CLOSED:",
              str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
