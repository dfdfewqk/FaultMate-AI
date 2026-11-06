"""Synthetic-only grouping tests; no original data, training or model evaluation."""
from copy import deepcopy

import numpy as np
import pytest

from scripts.audit_paderborn_assets import OFFICIAL_CONDITIONS
from scripts.compare_ki21_dev_conditions import (
    CURRENT_NAMES, DEV_DAMAGED, DEV_HEALTHY, compare_ki21_to_verified_development,
)
from scripts.extract_paderborn_unitless import FEATURE_NAMES


def _synthetic_fixture():
    model = {
        "mean": np.zeros(12), "scale": np.array([1.] * 6 + [.01] * 6),
        "coefs": np.array([.1] * 6 + [.2] * 6),
    }
    rows = []
    for i, asset in enumerate(sorted(DEV_HEALTHY | DEV_DAMAGED)):
        for ci, cond in enumerate(sorted(OFFICIAL_CONDITIONS)):
            for trial in range(20):
                if asset == "KA04" and ci == 0 and trial < 4:
                    continue  # four originally duplicated trial rows excluded
                value = i * 0.03 + ci * 0.2 + trial * 0.001
                rows.append({
                    "asset_id": asset,
                    "label": "healthy" if asset in DEV_HEALTHY else "damaged",
                    "condition": cond,
                    "features": [1.0] * 6 + [float(value)] * 6,
                })
    assert len(rows) == 796
    report = {
        "schema": "ki21_known_historical_current_scaler_diagnostic_v1",
        "pooled_input_reconstructed_exactly": True,
        "source_unique_signal_pairs": 80,
        "original_mat_recordings": 80,
        "new_independent_test": False,
        "production_model_approved": False,
        "safe_to_work": False,
        "condition_rows": [],
    }
    for ci, cond in enumerate(sorted(OFFICIAL_CONDITIONS)):
        value = ci * 0.2 + 0.11
        report["condition_rows"].append({
            "condition": cond,
            "original_mat_count": 20,
            "unique_signal_pairs": 20,
            "features": [{
                "feature": name,
                "raw_unitless_median": value,
                "raw_unitless_q25": value - .0003,
                "raw_unitless_q75": value + .0003,
                "condition_median_z_vs_training_bearing_scaler": value/.01,
            } for name in CURRENT_NAMES],
        })
    provenance = {
        "dev_assets": sorted(DEV_HEALTHY | DEV_DAMAGED),
        "test_asset_ids_excluded": ["K006", "KI18"],
        "unique_recordings": 796,
        "physical_bearings": 10,
        "source_physical_si_units_verified": False,
        "approved_for_runtime": False,
    }
    return report, rows, provenance, model


def test_grouped_reference_has_ten_physical_bearings_not_796_independent_tests():
    report, rows, provenance, model = _synthetic_fixture()
    result = compare_ki21_to_verified_development(report, rows, provenance, model)
    assert result["dev_physical_bearing_count"] == 10
    assert result["dev_original_unique_feature_records"] == 796
    assert result["ki21_not_used_for_model_training_or_feature_selection"] is True
    assert result["new_independent_healthy_cohort_measured"] is False
    assert result["accuracy_or_specificity_estimated"] is False
    assert result["production_ml_activation_allowed"] is False
    assert len(result["four_conditions"]) == 4
    for condition in result["four_conditions"]:
        assert condition["development_physical_bearings"] == 10
        assert condition["healthy_dev"] == 5
        assert condition["damaged_dev"] == 5
        assert len(condition["features"]) == 6
        for f in condition["features"]:
            assert f["development_healthy_physical_bearings"] == 5
            assert f["development_damaged_physical_bearings"] == 5
            assert 0 <= f["number_of_dev_bearings_with_lower_condition_median"] <= 10
            assert f["not_an_independent_accuracy_or_calibrated_outlier_test"] is True
            dispersion = f["within_bearing_trial_dispersion"]
            assert dispersion["trials_not_independent_bearings"] is True
            assert dispersion["not_an_independent_repeat_extraction_test"] is True
            assert dispersion["ki21_original_trials"] == 20
            assert dispersion["dev_bearings"] == 10
            assert dispersion["ki21_trial_iqr_unitless"] == pytest.approx(.0006)
            assert dispersion["ki21_trial_iqr_in_frozen_training_scale_units"] == pytest.approx(.06)
            assert dispersion["dev_ten_bearing_trial_iqr_median"] == pytest.approx(.0095)
            expected_min = .0075 if condition["condition"] == sorted(OFFICIAL_CONDITIONS)[0] else .0095
            assert dispersion["dev_ten_bearing_trial_iqr_min"] == pytest.approx(expected_min)
            assert dispersion["dev_ten_bearing_trial_iqr_max"] == pytest.approx(.0095)
            assert dispersion["ki21_trial_iqr_below_all_ten_dev_bearing_iqr"] is True


def test_nondev_or_ki21_data_must_not_enter_dev_reference():
    report, rows, provenance, model = _synthetic_fixture()
    malicious = deepcopy(rows)
    malicious[0]["asset_id"] = "KI21"
    with pytest.raises(ValueError, match="nondevelopment_asset"):
        compare_ki21_to_verified_development(report, malicious, provenance, model)
    forged = deepcopy(rows)
    forged[0]["asset_id"] = "K006"
    with pytest.raises(ValueError, match="nondevelopment_asset"):
        compare_ki21_to_verified_development(report, forged, provenance, model)
    forged = deepcopy(provenance)
    forged["dev_assets"] = ["KI21", *sorted(DEV_HEALTHY | DEV_DAMAGED)[:-1]]
    with pytest.raises(ValueError, match="wrong_or_leaking_development_reference"):
        compare_ki21_to_verified_development(report, rows, forged, model)


def test_ki21_scaler_z_forgery_and_incomplete_bearings_fail_closed():
    report, rows, provenance, model = _synthetic_fixture()
    bad = deepcopy(report)
    bad["condition_rows"][0]["features"][0]["condition_median_z_vs_training_bearing_scaler"] = 9999.
    with pytest.raises(ValueError, match="ki21_scaler_or_feature_value_mismatch"):
        compare_ki21_to_verified_development(bad, rows, provenance, model)
    bad = deepcopy(report)
    bad["source_unique_signal_pairs"] = 79
    with pytest.raises(ValueError, match="invalid_verified_ki21"):
        compare_ki21_to_verified_development(bad, rows, provenance, model)
    incomplete = deepcopy(rows)
    missing_condition = sorted(OFFICIAL_CONDITIONS)[0]
    removed = 0
    for r in incomplete:
        if r["asset_id"] == "K001" and r["condition"] == missing_condition:
            r["asset_id"] = "K002"
            removed += 1
    assert removed == 20
    with pytest.raises(ValueError, match="development_physical_bearing_condition_incomplete"):
        compare_ki21_to_verified_development(report, incomplete, provenance, model)


def test_label_and_nonfinite_features_cannot_pass_dev_reference():
    report, rows, provenance, model = _synthetic_fixture()
    bad = deepcopy(rows)
    bad[0]["label"] = "damaged"  # K001 always healthy
    with pytest.raises(ValueError, match="nondevelopment_asset_or_invalid_label"):
        compare_ki21_to_verified_development(report, bad, provenance, model)
    bad = deepcopy(rows)
    bad[0]["features"][6] = float("inf")
    with pytest.raises(ValueError, match="invalid_source_verified_development_features"):
        compare_ki21_to_verified_development(report, bad, provenance, model)


def test_invalid_quantiles_and_trial_order_report_consistency():
    report, rows, provenance, model = _synthetic_fixture()
    original = compare_ki21_to_verified_development(report, rows, provenance, model)
    # Shuffling the 796 derived record order should not alter any
    # physical-bearing grouped statistics; original report hashes remain
    # unchanged in the actual verified_dev_rows caller.
    shuffled = list(reversed(rows))
    again = compare_ki21_to_verified_development(report, shuffled, provenance, model)
    assert original == again
    malformed = deepcopy(report)
    malformed["condition_rows"][0]["features"][0]["raw_unitless_q25"] = float("nan")
    with pytest.raises(ValueError, match="invalid_verified_ki21_trial_quantiles"):
        compare_ki21_to_verified_development(malformed, rows, provenance, model)
    malformed = deepcopy(report)
    malformed["condition_rows"][0]["features"][0]["raw_unitless_q75"] = -2
    with pytest.raises(ValueError, match="invalid_verified_ki21_trial_quantiles"):
        compare_ki21_to_verified_development(malformed, rows, provenance, model)
