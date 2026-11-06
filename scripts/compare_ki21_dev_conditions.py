"""Descriptive KI21 current-feature reference against ten ORIGINAL development bearings.

The caller must FIRST authenticate original KI21 RAR + 80 paired MAT through
analyze_original_ki21_conditions(), and verify the *ten* prior source-feature
JSONs against pinned independent raw-audit SHA via verified_dev_rows().
This function NEVER trains/selects a model or treats known KI21 as fresh test.
The 10 training/development bearings are not a representative population and
are NOT independent normal validation data; same physical-bearing trials
are grouped before comparing. Single-condition medians are outside frozen
model's original 80-record pooled input contract.
"""
from __future__ import annotations

from collections import defaultdict
import math

import numpy as np

from scripts.audit_paderborn_assets import OFFICIAL_CONDITIONS
from scripts.extract_paderborn_unitless import FEATURE_NAMES

DEV_HEALTHY = frozenset({"K001", "K002", "K003", "K004", "K005"})
DEV_DAMAGED = frozenset({"KA04", "KA16", "KB23", "KI04", "KI16"})
DEV_ONLY = DEV_HEALTHY | DEV_DAMAGED
CURRENT_NAMES = tuple(name for name in FEATURE_NAMES if name.startswith("current_"))


def compare_ki21_to_verified_development(
    ki21_current_review: dict, dev_rows: list[dict],
    dev_provenance: dict, frozen: dict,
) -> dict:
    """Return condition-level bearing-reference comparisons, never new accuracy.

    dev_rows are *already* source/SHA verified by verified_dev_rows().
    KI21 readings must be derived in this same run from the original RAR,
    rather than trusting a user-supplied feature JSON as source identity.
    """
    if (not isinstance(ki21_current_review, dict)
        or ki21_current_review.get("schema") !=
           "ki21_known_historical_current_scaler_diagnostic_v1"
        or ki21_current_review.get("pooled_input_reconstructed_exactly") is not True
        or ki21_current_review.get("source_unique_signal_pairs") != 80
        or ki21_current_review.get("original_mat_recordings") != 80
        or ki21_current_review.get("new_independent_test") is not False
        or ki21_current_review.get("production_model_approved") is not False
        or ki21_current_review.get("safe_to_work") is not False):
        raise ValueError("invalid_verified_ki21_condition_reference")
    if (not isinstance(dev_provenance, dict)
        or set(dev_provenance.get("dev_assets", [])) != DEV_ONLY
        or len(dev_provenance.get("dev_assets", [])) != 10
        or dev_provenance.get("test_asset_ids_excluded") != ["K006", "KI18"]
        or dev_provenance.get("unique_recordings") != 796
        or dev_provenance.get("physical_bearings") != 10
        or dev_provenance.get("source_physical_si_units_verified") is not False
        or dev_provenance.get("approved_for_runtime") is not False):
        raise ValueError("wrong_or_leaking_development_reference")
    mean = np.asarray(frozen["mean"], dtype=float)
    scale = np.asarray(frozen["scale"], dtype=float)
    coeff = np.asarray(frozen["coefs"], dtype=float)
    if (any(v.shape != (len(FEATURE_NAMES),) for v in (mean, scale, coeff))
        or any(not np.all(np.isfinite(v)) for v in (mean, scale, coeff))
        or np.any(scale <= 0)
        or len(CURRENT_NAMES) != 6):
        raise ValueError("invalid_frozen_model_reference")

    if not isinstance(dev_rows, list) or len(dev_rows) != 796:
        raise ValueError("development_unique_record_count_mismatch")
    grouped: dict[str, dict[str, list[list[float]]]] = defaultdict(
        lambda: defaultdict(list))
    labels = {}
    for record in dev_rows:
        if not isinstance(record, dict):
            raise ValueError("invalid_development_record")
        asset = record.get("asset_id")
        condition = record.get("condition")
        label = record.get("label")
        if (asset not in DEV_ONLY or condition not in OFFICIAL_CONDITIONS
            or label != ("healthy" if asset in DEV_HEALTHY else "damaged")
            or (asset in labels and labels[asset] != label)):
            raise ValueError("nondevelopment_asset_or_invalid_label")
        labels[asset] = label
        values = record.get("features")
        if (not isinstance(values, list) or len(values) != len(FEATURE_NAMES)
            or any(type(x) not in (int, float) or not math.isfinite(x)
                   for x in values)):
            raise ValueError("invalid_source_verified_development_features")
        grouped[condition][asset].append([float(v) for v in values])
    if (set(labels) != DEV_ONLY or set(grouped) != OFFICIAL_CONDITIONS
        or any(set(grouped[condition]) != DEV_ONLY
               for condition in OFFICIAL_CONDITIONS)
        or any(not 16 <= len(grouped[condition][asset]) <= 20
               for condition in OFFICIAL_CONDITIONS for asset in DEV_ONLY)):
        raise ValueError("development_physical_bearing_condition_incomplete")

    current_index = {name: FEATURE_NAMES.index(name) for name in CURRENT_NAMES}
    ki21_conditions = ki21_current_review.get("condition_rows")
    if (not isinstance(ki21_conditions, list)
        or len(ki21_conditions) != 4
        or {r.get("condition") for r in ki21_conditions} != OFFICIAL_CONDITIONS):
        raise ValueError("invalid_ki21_condition_inventory")
    ki21_by_condition = {r["condition"]: r for r in ki21_conditions}
    results = []
    for condition in sorted(OFFICIAL_CONDITIONS):
        bearing_medians = {
            asset: np.median(np.asarray(grouped[condition][asset], dtype=float),
                             axis=0)
            for asset in sorted(DEV_ONLY)
        }
        # Trial-to-trial dispersion uses each physical bearing only once
        # in between-bearing summaries. 16-20 repeated source MAT records
        # are NOT 16-20 independent physical bearings and DO NOT verify
        # deterministic re-extraction from original archive bytes.
        bearing_trial_iqr = {
            asset: np.subtract(
                *np.quantile(np.asarray(grouped[condition][asset], dtype=float),
                             [.75, .25], axis=0)
            )
            for asset in sorted(DEV_ONLY)
        }
        cond = ki21_by_condition[condition]
        ki21_values = cond.get("features")
        if (not isinstance(ki21_values, list)
            or len(ki21_values) != 6
            or {x.get("feature") for x in ki21_values} != set(CURRENT_NAMES)
            or cond.get("original_mat_count") != 20
            or cond.get("unique_signal_pairs") != 20):
            raise ValueError("invalid_original_ki21_current_feature_rows")
        features = []
        for row in ki21_values:
            name = row["feature"]
            idx = current_index[name]
            observed = row.get("raw_unitless_median")
            z_observed = row.get("condition_median_z_vs_training_bearing_scaler")
            if (type(observed) not in (int, float)
                or type(z_observed) not in (int, float)
                or not math.isfinite(observed) or not math.isfinite(z_observed)
                or not math.isclose(
                    (observed-mean[idx])/scale[idx], z_observed,
                    abs_tol=1e-8, rel_tol=1e-10)):
                raise ValueError("ki21_scaler_or_feature_value_mismatch")
            healthy = [float(bearing_medians[a][idx])
                       for a in sorted(DEV_HEALTHY)]
            damaged = [float(bearing_medians[a][idx])
                       for a in sorted(DEV_DAMAGED)]
            all_dev = healthy + damaged
            ki21_q25 = row.get("raw_unitless_q25")
            ki21_q75 = row.get("raw_unitless_q75")
            if (type(ki21_q25) not in (int, float)
                or type(ki21_q75) not in (int, float)
                or not math.isfinite(ki21_q25) or not math.isfinite(ki21_q75)
                or ki21_q75 < ki21_q25):
                raise ValueError("invalid_verified_ki21_trial_quantiles")
            ki21_iqr = float(ki21_q75 - ki21_q25)
            healthy_trial_iqr = [
                float(bearing_trial_iqr[a][idx]) for a in sorted(DEV_HEALTHY)
            ]
            damaged_trial_iqr = [
                float(bearing_trial_iqr[a][idx]) for a in sorted(DEV_DAMAGED)
            ]
            all_dev_trial_iqr = healthy_trial_iqr + damaged_trial_iqr
            features.append({
                "feature": name,
                "ki21_condition_median_unitless": float(observed),
                "ki21_z_vs_frozen_development_bearing_scaler": float(z_observed),
                "development_healthy_physical_bearings": 5,
                "development_damaged_physical_bearings": 5,
                "healthy_dev_condition_medians_min": min(healthy),
                "healthy_dev_condition_medians_median": float(np.median(healthy)),
                "healthy_dev_condition_medians_max": max(healthy),
                "damaged_dev_condition_medians_min": min(damaged),
                "damaged_dev_condition_medians_median": float(np.median(damaged)),
                "damaged_dev_condition_medians_max": max(damaged),
                "all_dev_condition_medians_min": min(all_dev),
                "all_dev_condition_medians_max": max(all_dev),
                "ki21_below_all_dev_observed_range": observed < min(all_dev),
                "ki21_above_all_dev_observed_range": observed > max(all_dev),
                "number_of_dev_bearings_with_lower_condition_median": sum(
                    value < observed for value in all_dev),
                "within_bearing_trial_dispersion": {
                    "meaning": "repeat_original_mat_features_within_one_physical_bearing",
                    "ki21_original_trials": 20,
                    "dev_bearings": 10,
                    "ki21_trial_iqr_unitless": ki21_iqr,
                    "ki21_trial_iqr_in_frozen_training_scale_units": float(
                        ki21_iqr / scale[idx]),
                    "healthy_dev_five_bearing_trial_iqr_median": float(
                        np.median(healthy_trial_iqr)),
                    "damaged_dev_five_bearing_trial_iqr_median": float(
                        np.median(damaged_trial_iqr)),
                    "dev_ten_bearing_trial_iqr_min": min(all_dev_trial_iqr),
                    "dev_ten_bearing_trial_iqr_median": float(
                        np.median(all_dev_trial_iqr)),
                    "dev_ten_bearing_trial_iqr_max": max(all_dev_trial_iqr),
                    "ki21_trial_iqr_below_all_ten_dev_bearing_iqr": (
                        ki21_iqr < min(all_dev_trial_iqr)),
                    "ki21_trial_iqr_above_all_ten_dev_bearing_iqr": (
                        ki21_iqr > max(all_dev_trial_iqr)),
                    "trials_not_independent_bearings": True,
                    "not_an_independent_repeat_extraction_test": True,
                    "not_a_calibrated_variance_or_sensor_stability_test": True,
                },
                "not_an_independent_accuracy_or_calibrated_outlier_test": True,
            })
        features.sort(key=lambda r: CURRENT_NAMES.index(r["feature"]))
        results.append({
            "condition": condition,
            "development_physical_bearings": 10,
            "healthy_dev": 5,
            "damaged_dev": 5,
            "ki21_previously_opened_not_a_development_or_fresh_test_bearing": True,
            "features": features,
        })
    return {
        "schema": "faultmate_ki21_10_dev_current_condition_reference_v1",
        "source_dev_original_sha_verification_is_precondition": True,
        "replay_ki21_original_rar_in_same_run_is_precondition": True,
        "dev_physical_bearing_count": 10,
        "dev_original_unique_feature_records": 796,
        "ki21_original_mat_recordings": 80,
        "frozen_training_input": "10_dev_bearing_full_80_record_medians",
        "reference_is_condition_median_per_physical_bearing_not_trial_level": True,
        "four_conditions": results,
        "ki21_not_used_for_model_training_or_feature_selection": True,
        "new_independent_healthy_cohort_measured": False,
        "accuracy_or_specificity_estimated": False,
        "model_refitted_or_threshold_changed": False,
        "production_ml_activation_allowed": False,
        "source_license": "CC BY-NC 4.0",
    }
