"""Read-only current-feature scaler/dispersion audit for known KI21 replay.

For the authentic original KI21 case, the caller MUST first run
extract_unseen() and validate_prior_damaged_report(). This helper only
summarizes validated dimensionless features, comparing condition medians with
the frozen training *bearing-level pooled-median* scaler. Standardized scores
on individual condition records are NOT calibrated OOD or field safety tests.
No training, threshold adjustments, source changes or API activation.
"""
from __future__ import annotations

from collections import defaultdict
import math

import numpy as np

from scripts.audit_paderborn_assets import OFFICIAL_CONDITIONS
from scripts.extract_paderborn_unitless import FEATURE_NAMES

CURRENT_INDEX = tuple(i for i, name in enumerate(FEATURE_NAMES)
                      if name.startswith("current_"))


def describe_current_scaler_dispersion(
    report: dict, frozen: dict, verified_pooled: np.ndarray
) -> dict:
    """Quantiles and exact additive logit terms; pure descriptive arithmetic.

    A synthetic report passed by a unit test is NOT source authentication.
    Source identity, MD5 and all raw signal checks happen in the caller.
    """
    mean = np.asarray(frozen["mean"], dtype=float)
    scale = np.asarray(frozen["scale"], dtype=float)
    coeff = np.asarray(frozen["coefs"], dtype=float)
    pooled = np.asarray(verified_pooled, dtype=float)
    if (any(x.shape != (len(FEATURE_NAMES),) for x in (mean, scale, coeff, pooled))
        or not all(np.all(np.isfinite(x)) for x in (mean, scale, coeff, pooled))
        or np.any(scale <= 0)
        or CURRENT_INDEX != tuple(range(6, 12))):
        raise ValueError("invalid_frozen_current_scaler_contract")
    if not isinstance(report, dict) or not isinstance(report.get("records"), list):
        raise ValueError("validated_original_feature_records_required")

    groups: dict[str, list[list[float]]] = defaultdict(list)
    seen_trials: dict[str, set[int]] = defaultdict(set)
    pooled_data: list[list[float]] = []
    for row in report["records"]:
        if not isinstance(row, dict):
            raise ValueError("invalid_feature_row")
        cond, trial = row.get("condition"), row.get("trial")
        if (cond not in OFFICIAL_CONDITIONS or type(trial) is not int
            or not 1 <= trial <= 20 or trial in seen_trials[cond]):
            raise ValueError("invalid_condition_or_trial")
        seen_trials[cond].add(trial)
        if row.get("duplicate_of") is not None:
            if row.get("values") is not None:
                raise ValueError("duplicate_feature_reuse")
            continue
        values = row.get("values")
        if (not isinstance(values, list) or len(values) != len(FEATURE_NAMES)
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)):
            raise ValueError("invalid_unitless_record_features")
        groups[cond].append(values)
        pooled_data.append(values)

    if (len(report["records"]) != 80
        or set(seen_trials) != OFFICIAL_CONDITIONS
        or any(seen_trials[c] != set(range(1, 21)) for c in OFFICIAL_CONDITIONS)
        or any(not groups[c] for c in OFFICIAL_CONDITIONS)
        or len(pooled_data) < 60):
        raise ValueError("incomplete_four_condition_source")
    if not np.array_equal(np.median(np.asarray(pooled_data), axis=0), pooled):
        raise ValueError("frozen_pooled_vector_changed")

    rows = []
    for condition in sorted(OFFICIAL_CONDITIONS):
        matrix = np.asarray(groups[condition], dtype=float)
        features = []
        for idx in CURRENT_INDEX:
            data = matrix[:, idx]
            q05, q25, median, q75, q95 = np.quantile(
                data, [.05, .25, .50, .75, .95])
            z = float((median - mean[idx]) / scale[idx])
            pooled_z = float((pooled[idx] - mean[idx]) / scale[idx])
            signed_delta = float((median - pooled[idx]) / scale[idx] * coeff[idx])
            features.append({
                "feature": FEATURE_NAMES[idx],
                "original_trials": 20,
                "unique_signal_pairs_in_condition": len(matrix),
                "reference_is_training_bearing_level_median_scaler": True,
                "frozen_training_bearing_scaler_mean": float(mean[idx]),
                "frozen_training_bearing_scaler_scale": float(scale[idx]),
                "raw_unitless_q05": float(q05),
                "raw_unitless_q25": float(q25),
                "raw_unitless_median": float(median),
                "raw_unitless_q75": float(q75),
                "raw_unitless_q95": float(q95),
                "condition_median_z_vs_training_bearing_scaler": z,
                "pooled_bearing_median_z_vs_training_bearing_scaler": pooled_z,
                "condition_iqr_in_training_scaler_units": float((q75 - q25) / scale[idx]),
                "condition_median_z_shift_vs_pooled": z - pooled_z,
                "logit_contribution_shift_vs_pooled": signed_delta,
                "abs_condition_median_z_over_three_descriptive_only": abs(z) > 3,
            })
        rows.append({
            "condition": condition,
            "original_mat_count": 20,
            "unique_signal_pairs": len(matrix),
            "features": features,
            "sum_current_logit_shift_vs_pooled": float(math.fsum(
                f["logit_contribution_shift_vs_pooled"] for f in features)),
        })

    return {
        "schema": "ki21_known_historical_current_scaler_diagnostic_v1",
        "pooled_input_reconstructed_exactly": True,
        "condition_rows": rows,
        "original_mat_recordings": 80,
        "source_unique_signal_pairs": len(pooled_data),
        "frozen_model_changed": False,
        "frozen_threshold_changed": False,
        "new_independent_test": False,
        "training_reference_scope": "10_previously_used_physical_bearing_pooled_medians",
        "condition_record_distribution_not_equivalent_to_training_distribution": True,
        "three_std_flag_is_descriptive_not_calibrated_outlier_threshold": True,
        "model_feature_attribution_not_physical_sensor_diagnosis": True,
        "production_model_approved": False,
        "safe_to_work": False,
    }
