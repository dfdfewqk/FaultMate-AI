"""Fail-closed source-metadata gate for *independent* healthy bearing validation.

This is NOT an ML inference endpoint and never downloads data or performs
predictions. It evaluates provenance & acquisition compatibility of reviewed
PUBLIC source descriptions before any numerical external evaluation is
permitted. No source is eligible merely because it has "healthy" recordings.

A new input protocol/independent validation must be reviewed separately for
any cross-domain data; existing 4-condition Paderborn model cannot accept
3-load KAIST, variable-speed KAIST, nor PHM24/BJTU railway data as drop-in assets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = ROOT / "docs" / "EXTERNAL_HEALTHY_SOURCE_CANDIDATES_20261105.json"
BASELINE_ASSETS = frozenset({"K001", "K002", "K003", "K004", "K005", "K006"})
BASELINE_CONDITIONS = frozenset({
    "N09_M07_F10", "N15_M01_F10", "N15_M07_F04", "N15_M07_F10"})
PINNED_MODEL = "84a7c059fa769d1b0e2bd0075ecba92bcd06ae24acf961e0ea2120d9d44a0ab0"

# These facts are from original primary documentation, not ML test outcomes.
EXPECTED_CANDIDATES = {
    "paderborn_healthy_reuse": {
        "url": "https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download",
        "license": "CC BY-NC 4.0", "vib_hz": 64000, "cur_hz": 64000,
        "conditions": 4, "match": True, "independent_site": False,
    },
    "kaist_varying_load": {
        "url": "https://data.mendeley.com/datasets/ztmf3m7h5x",
        "license": "CC BY 4.0", "vib_hz": 25600, "cur_hz": 50000,
        "conditions": 3, "match": False, "independent_site": True,
    },
    "kaist_varying_speed": {
        "url": "https://data.mendeley.com/datasets/vxkj334rzv",
        "license": "CC BY 4.0", "vib_hz": 25600, "cur_hz": 100000,
        "conditions": None, "match": False, "independent_site": True,
    },
    "phm24_bjtu_rao_bogie": {
        "url": "https://academic.oup.com/tse/article/8/2/tdag011/8644296",
        "license": "not_verified_for_source_data",
        "vib_hz": 64000, "cur_hz": 64000,
        "conditions": 9, "match": False, "independent_site": True,
    },
}


class SourceReadinessError(ValueError):
    pass


def _validate_fixed_source_inventory(doc: dict) -> None:
    if not isinstance(doc, dict) or doc.get("schema") != "faultmate_external_healthy_candidate_metadata_v1":
        raise SourceReadinessError("unexpected_external_source_inventory_schema")
    base = doc.get("baseline")
    if not isinstance(base, dict):
        raise SourceReadinessError("missing_original_model_contract")
    if (base.get("research_model_sha256") != PINNED_MODEL
        or set(base.get("healthy_physical_asset_ids_already_opened", [])) != BASELINE_ASSETS
        or len(base["healthy_physical_asset_ids_already_opened"]) != 6
        or base.get("nominal_sample_rate_vibration_hz") != 64000
        or base.get("nominal_sample_rate_current_hz") != 64000
        or set(base.get("required_distinct_conditions", [])) != BASELINE_CONDITIONS
        or len(base["required_distinct_conditions"]) != 4
        or base.get("recordings_per_condition") != 20
        or base.get("bearing_type") != "6203"
        or base.get("paired_signal_roles") != ["vibration_1", "phase_current_1"]):
        raise SourceReadinessError("original_paderborn_provenance_or_input_contract_changed")
    rows = doc.get("candidates")
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_CANDIDATES):
        raise SourceReadinessError("candidate_source_list_changed_without_review")
    if (len({r.get("source_id") for r in rows if isinstance(r, dict)})
        != len(EXPECTED_CANDIDATES)):
        raise SourceReadinessError("candidate_id_duplicate_or_invalid")
    if {r.get("source_id") for r in rows if isinstance(r, dict)} != set(EXPECTED_CANDIDATES):
        raise SourceReadinessError("candidate_source_identity_changed")
    for row in rows:
        if not isinstance(row, dict):
            raise SourceReadinessError("invalid_source_metadata")
        src = EXPECTED_CANDIDATES[row["source_id"]]
        for key, expected in (
            ("source_url", src["url"]),
            ("license", src["license"]),
            ("nominal_sample_rate_vibration_hz", src["vib_hz"]),
            ("nominal_sample_rate_current_hz", src["cur_hz"]),
            ("operating_condition_count", src["conditions"]),
            ("matched_paderborn_condition_protocol", src["match"]),
            ("independent_data_acquisition_site", src["independent_site"]),
        ):
            # Enforce not only truthiness; None and bool/ints are distinct here.
            if type(row.get(key)) is not type(expected) or row.get(key) != expected:
                raise SourceReadinessError(
                    "reviewed_source_fact_conflict:" + row["source_id"] + ":" + key)
        if row.get("healthy_reference_reported") is not True:
            raise SourceReadinessError("not_a_healthy_reference_source")
        if row.get("paired_vibration_motor_current") is not True:
            raise SourceReadinessError("paired_sensor_roles_missing")
    reused = next(r for r in rows if r["source_id"] == "paderborn_healthy_reuse")
    if (reused.get("physical_healthy_asset_ids") != sorted(BASELINE_ASSETS)
        or reused.get("independent_physical_asset_inventory_verified") is not True
        or reused.get("source_archive_integrity_verified") is not True
        or reused.get("source_raw_signal_integrity_verified") is not True):
        raise SourceReadinessError("paderborn_known_six_reused_not_new")
    phm = next(r for r in rows if r["source_id"] == "phm24_bjtu_rao_bogie")
    # The publication's CC BY article license does NOT establish dataset
    # reuse rights or prove the exact raw competition files were downloaded.
    if (phm.get("original_download_and_usage_terms_verified") is not False
        or phm.get("primary_evidence")
            != "2026 Oxford Academic PHM24 paper and 2025 BJTU-RAO experiment paper"
        or phm.get("additional_evidence_url") != "https://doi.org/10.1108/SRT-11-2024-0017"
        or phm.get("source_distribution_review_url")
            != "https://github.com/jonathanadamrico/BJTU_PHM_Beijing_Benchmark"):
        raise SourceReadinessError("phm24_source_license_or_original_evidence_unverified")
    for row in rows:
        if row["source_id"] == "paderborn_healthy_reuse":
            continue
        if (row.get("physical_healthy_asset_ids") is not None
            or row.get("independent_physical_asset_inventory_verified") is not False
            or row.get("source_archive_integrity_verified") is not False
            or row.get("source_raw_signal_integrity_verified") is not False
            or row.get("source_conditions_per_asset_verified") is not False
            or row.get("other_domain_equivalence_reviewed") is not False):
            raise SourceReadinessError("external_physical_asset_evidence_not_collected")


def assess_source_metadata(row: dict) -> dict:
    """Returns blockers only. Never approves model scores from metadata."""
    source_id = row["source_id"]
    blockers: list[str] = []
    identifiers = row.get("physical_healthy_asset_ids")
    if source_id == "paderborn_healthy_reuse":
        blockers.append("all_healthy_physical_bearings_already_opened")
    elif not isinstance(identifiers, list) or not identifiers:
        blockers.append("new_independent_healthy_physical_bearings_not_proven")
    if isinstance(identifiers, list) and set(identifiers) & BASELINE_ASSETS:
        blockers.append("previously_used_bearing_in_new_test")
    if row.get("independent_physical_asset_inventory_verified") is not True:
        blockers.append("per_bearing_asset_identity_not_audited")
    if (row.get("source_archive_integrity_verified") is not True
        or row.get("source_raw_signal_integrity_verified") is not True):
        blockers.append("original_measurement_hashes_not_verified")
    if row.get("source_conditions_per_asset_verified") is not True:
        blockers.append("four_conditions_20_trials_per_bearing_not_source_verified")
    if row.get("nominal_sample_rate_vibration_hz") != 64000:
        blockers.append("vibration_sampling_rate_differs_from_paderborn_64khz")
    if row.get("nominal_sample_rate_current_hz") != 64000:
        blockers.append("current_sampling_rate_differs_from_paderborn_64khz")
    if (row.get("matched_paderborn_condition_protocol") is not True
        or row.get("operating_condition_count") != 4):
        blockers.append("four_paderborn_operating_conditions_not_equivalent")
    if row.get("independent_data_acquisition_site") is True:
        if row.get("other_domain_equivalence_reviewed") is not True:
            blockers.append("independent_site_domain_shift_not_reviewed")
    if source_id == "phm24_bjtu_rao_bogie":
        blockers.extend([
            "official_original_bearing_files_not_audited",
            "per_asset_axlebox_healthy_label_and_unique_bearing_id_not_verified",
            "source_data_usage_license_and_release_access_unverified",
            "phm24_and_bjtu_rao_benchmark_overlap_not_audited",
        ])
    # Even a fully grounded candidate must undergo separate *actual*
    # technical and scientific review before any model predicts. This API is
    # only a metadata evidence report, never an approval system.
    blockers.append("actual_independent_normal_evaluation_not_performed")
    return {
        "source_id": source_id,
        "metadata_reviewed": True,
        "new_independent_healthy_qualification": False,
        "direct_frozen_model_prediction_allowed": False,
        "healthy_specificity_measured": False,
        "false_positive_rate_measured": False,
        "blocking_reasons": blockers,
    }


def assess_inventory(path: Path = SOURCE_FILE) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    _validate_fixed_source_inventory(document)
    results = [assess_source_metadata(r) for r in document["candidates"]]
    return {
        "schema": "faultmate_external_healthy_compatibility_result_v1",
        "status": "additional_original_independent_healthy_measurements_required",
        "model_status": "experimental_unapproved_not_for_runtime",
        "no_approved_healthy_source": True,
        "new_healthy_bearings_validated": 0,
        "overall_accuracy_measured": False,
        "false_positive_rate_measured": False,
        "source_metadata_not_original_recording_evidence": True,
        "paid_api_invoked": False,
        "ml_predictions_performed": False,
        "results": results,
        "action_required": (
            "Obtain newly measured independent healthy physical bearings with "
            "both raw sensor signals and traceable operating-condition and "
            "recording/provenance evidence, or separately develop and validate "
            "an explicit new external-domain benchmark. Do not run the frozen "
            "Paderborn classifier against incompatible sources."
        ),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", type=Path, default=SOURCE_FILE)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = assess_inventory(args.inventory)
        if args.out.exists():
            raise SourceReadinessError("refuse_overwrite_prior_source_assessment")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
            output.write("\n")
        print(json.dumps({
            "status": result["status"],
            "candidate_sources": len(result["results"]),
            "new_healthy_bearings_validated": 0,
            "false_alarm_rate_measured": False,
            "runtime_model_activated": False,
        }))
        return 0
    except (OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as exc:
        print("EXTERNAL_HEALTHY_SOURCE_PREFLIGHT_FAIL_CLOSED:", str(exc),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
