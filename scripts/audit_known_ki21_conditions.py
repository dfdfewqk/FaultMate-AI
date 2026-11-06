"""Read-only KI21 four-condition/20-trial aggregation sensitivity audit.

Replays the EXACT previously opened original KI21 RAR (official MD5 and all
paired MATLAB raw signals), never a fresh held-out model test. Per-condition
scores are deliberately labeled out-of-training-contract diagnostics: the
frozen logistic model was fitted to ONE 4-condition bearing-median vector,
not to individual operating conditions. No refit, threshold change or
physical fault claim. Raw signals and user data are never persisted.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_paderborn_assets import OFFICIAL_CONDITIONS
from scripts.evaluate_unseen_paderborn_damaged import frozen_coefficients
from scripts.extract_paderborn_unitless import FEATURE_NAMES
from scripts.extract_unseen_paderborn_damaged import extract_unseen
from scripts.explain_known_ki21_frozen_model import explain_frozen_logit
from scripts.replay_prior_damaged_bearing import (
    KNOWN_HISTORICAL_MISS, score_prior_damaged_report,
    validate_prior_damaged_report,
)


def _channel_logit_terms(attribution: dict) -> tuple[float, float]:
    terms = {row["feature"]: row["signed_logit_contribution"]
             for row in attribution["features_sorted_by_absolute_logit_contribution"]}
    return (
        math.fsum(float(terms[k]) for k in FEATURE_NAMES[:6]),
        math.fsum(float(terms[k]) for k in FEATURE_NAMES[6:]),
    )


def compare_verified_condition_records(
    doc: dict, model: dict, verified_pooled_vector: np.ndarray
) -> dict:
    """Arithmetic only; caller MUST authenticate and fully validate source.

    Synthetic-only tests may call this function with synthetic records. Never
    label that as actual original measurements or new scientific evidence.
    """
    if not isinstance(doc, dict) or not isinstance(doc.get("records"), list):
        raise ValueError("verified_feature_records_required")
    groups: dict[str, list[list[float]]] = defaultdict(list)
    trials: dict[str, set[int]] = defaultdict(set)
    all_unique: list[list[float]] = []
    for record in doc["records"]:
        if not isinstance(record, dict):
            raise ValueError("invalid_condition_feature_record")
        cond, trial = record.get("condition"), record.get("trial")
        if (cond not in OFFICIAL_CONDITIONS or type(trial) is not int
            or not 1 <= trial <= 20 or trial in trials[cond]):
            raise ValueError("invalid_condition_trial")
        trials[cond].add(trial)
        if record.get("duplicate_of") is not None:
            if record.get("values") is not None:
                raise ValueError("duplicate_must_not_contribute_features")
            continue
        values = record.get("values")
        if (not isinstance(values, list) or len(values) != len(FEATURE_NAMES)
            or any(type(x) not in (int, float) or not math.isfinite(x)
                   for x in values)):
            raise ValueError("invalid_condition_feature_vector")
        vector = [float(x) for x in values]
        groups[cond].append(vector)
        all_unique.append(vector)
    if (len(doc["records"]) != 80 or set(trials) != OFFICIAL_CONDITIONS
        or any(trials[key] != set(range(1, 21)) for key in OFFICIAL_CONDITIONS)
        or len(all_unique) < 60 or len(groups) != 4
        or any(len(groups[c]) == 0 for c in OFFICIAL_CONDITIONS)):
        raise ValueError("incomplete_four_condition_feature_inventory")

    pooled = np.median(np.asarray(all_unique, dtype=float), axis=0)
    verified = np.asarray(verified_pooled_vector, dtype=float)
    if verified.shape != pooled.shape or not np.array_equal(pooled, verified):
        raise ValueError("condition_reaggregation_differs_from_original_frozen_input")

    full = explain_frozen_logit(verified, model)
    full_vib, full_current = _channel_logit_terms(full)
    full_terms = {entry["feature"]: entry["signed_logit_contribution"]
                  for entry in full["features_sorted_by_absolute_logit_contribution"]}
    rows = []
    for cond in sorted(OFFICIAL_CONDITIONS):
        cond_vector = np.median(np.asarray(groups[cond], dtype=float), axis=0)
        alternate = explain_frozen_logit(cond_vector, model)
        vib, current = _channel_logit_terms(alternate)
        change_terms = sorted([
            {
                "feature": entry["feature"],
                "logit_contribution_change_vs_pooled": (
                    entry["signed_logit_contribution"] - full_terms[entry["feature"]]
                ),
            }
            for entry in alternate["features_sorted_by_absolute_logit_contribution"]
        ], key=lambda entry: abs(entry["logit_contribution_change_vs_pooled"]),
           reverse=True)
        rows.append({
            "condition": cond,
            "original_mat_count": 20,
            "unique_signal_pairs": len(groups[cond]),
            "duplicates_excluded": 20 - len(groups[cond]),
            "diagnostic_condition_median_logit": alternate["logit"],
            "diagnostic_condition_median_damage_score": alternate["damage_model_score"],
            "diagnostic_condition_median_label": alternate["prediction"],
            "vibration_logit_contribution": vib,
            "current_logit_contribution": current,
            "logit_difference_from_frozen_pooled": alternate["logit"] - full["logit"],
            "largest_three_feature_contribution_differences": change_terms[:3],
            "not_a_validated_per_condition_prediction": True,
        })
    return {
        "frozen_pooled_logit": full["logit"],
        "frozen_pooled_score": full["damage_model_score"],
        "frozen_pooled_label": full["prediction"],
        "pooled_vibration_logit_contribution": full_vib,
        "pooled_current_logit_contribution": full_current,
        "pooled_source_unique_signal_pairs": len(all_unique),
        "original_80_record_pooled_median_reconstructed_exactly": True,
        "four_operating_conditions": rows,
        "condition_only_model_scores_outside_original_training_contract": True,
        "condition_median_replaces_80_record_median_only_in_diagnostic": True,
        "new_independent_data_or_accuracy_measured": False,
    }


def analyze_original_ki21_conditions(archive: Path, *, sevenzip: str) -> dict:
    # Full source identity, MD5, complete 80 MAT source checks, label and
    # raw duplicate/feature guards are delegated to the ORIGINAL routines.
    doc = extract_unseen(
        archive.absolute(), KNOWN_HISTORICAL_MISS, sevenzip=sevenzip)
    pooled_vector, info = validate_prior_damaged_report(doc)
    reference = score_prior_damaged_report(doc)
    frozen = frozen_coefficients()
    result = compare_verified_condition_records(doc, frozen, pooled_vector)
    if (reference["experimental_predicted_label"] != result["frozen_pooled_label"]
        or abs(reference["experimental_damage_model_score"] -
               result["frozen_pooled_score"]) > 0.000000011
        or reference["historical_false_negative"] is not True
        or result["pooled_source_unique_signal_pairs"] != info["source_unique_signal_pairs"]):
        raise ValueError("ki21_historical_80_record_reference_mismatch")
    return {
        "status": "known_ki21_condition_aggregation_diagnostic_only",
        "bearing_id": KNOWN_HISTORICAL_MISS,
        "physical_research_truth": "damaged",
        "official_original_archive_md5_and_80_mat_verified_this_run": True,
        "source_mat_recordings": info["source_mat_recordings"],
        "frozen_model_sha256": reference["frozen_model_sha256"],
        **result,
        "previously_opened_ki21_not_new_independent_test": True,
        "model_refitted_or_threshold_modified": False,
        "production_model_approved": False,
        "safe_to_work": False,
        "physical_si_units_verified": False,
        "source_license": "CC BY-NC 4.0",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sevenzip", default=None)
    args = parser.parse_args()
    tool = args.sevenzip or shutil.which("7z") or shutil.which("7zz")
    if not tool and sys.platform == "win32":
        candidate = Path(r"C:\Program Files\7-Zip\7z.exe")
        tool = str(candidate) if candidate.is_file() else None
    if not tool:
        parser.error("existing_7zip_required")
    doc = analyze_original_ki21_conditions(args.archive, sevenzip=tool)
    print(json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
