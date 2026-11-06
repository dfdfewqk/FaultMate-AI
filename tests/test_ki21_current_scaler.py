"""Synthetic arithmetic tests: not real bearing data, not model validation."""
from copy import deepcopy

import numpy as np
import pytest

from scripts.audit_paderborn_assets import OFFICIAL_CONDITIONS
from scripts.audit_known_ki21_current_scaler import describe_current_scaler_dispersion
from scripts.extract_paderborn_unitless import FEATURE_NAMES


def _fixtures():
    n = len(FEATURE_NAMES)
    mean = np.zeros(n)
    scale = np.ones(n)
    scale[6:] = 0.01
    model = {
        "mean": mean, "scale": scale,
        "coefs": np.array([0.2] * 6 + [-0.25] * 6),
        "intercept": 0., "threshold": 0.5,
    }
    records = []
    for i, condition in enumerate(sorted(OFFICIAL_CONDITIONS)):
        for trial in range(1, 21):
            values = [float(i * .1 + trial * .001)] * 6 + [
                float((i - 1.5) * .02 + trial * .0001)
            ] * 6
            records.append({
                "condition": condition, "trial": trial,
                "duplicate_of": None, "values": values,
            })
    doc = {"records": records}
    pooled = np.median(np.asarray([r["values"] for r in records]), axis=0)
    return doc, model, pooled


def test_four_condition_current_summaries_reproduce_frozen_reference():
    doc, model, pooled = _fixtures()
    result = describe_current_scaler_dispersion(doc, model, pooled)
    assert result["pooled_input_reconstructed_exactly"] is True
    assert result["original_mat_recordings"] == 80
    assert result["source_unique_signal_pairs"] == 80
    assert result["training_reference_scope"] == "10_previously_used_physical_bearing_pooled_medians"
    assert result["new_independent_test"] is False
    assert result["production_model_approved"] is False
    assert result["safe_to_work"] is False
    assert len(result["condition_rows"]) == 4
    for row in result["condition_rows"]:
        assert row["original_mat_count"] == 20
        assert row["unique_signal_pairs"] == 20
        assert len(row["features"]) == 6
        for f in row["features"]:
            assert f["feature"].startswith("current_")
            assert f["raw_unitless_q05"] <= f["raw_unitless_q25"] <= (
                f["raw_unitless_median"]) <= f["raw_unitless_q75"] <= f["raw_unitless_q95"]
            assert f["frozen_training_bearing_scaler_scale"] == pytest.approx(.01)
            expected_z = (f["raw_unitless_median"] -
                          f["frozen_training_bearing_scaler_mean"]) / .01
            assert f["condition_median_z_vs_training_bearing_scaler"] == pytest.approx(expected_z)
            assert f["condition_median_z_shift_vs_pooled"] == pytest.approx(
                expected_z - f["pooled_bearing_median_z_vs_training_bearing_scaler"])
            assert f["logit_contribution_shift_vs_pooled"] == pytest.approx(
                f["condition_median_z_shift_vs_pooled"] * -.25)
        assert row["sum_current_logit_shift_vs_pooled"] == pytest.approx(
            sum(f["logit_contribution_shift_vs_pooled"] for f in row["features"]))


def test_descriptive_large_z_is_not_model_approval():
    doc, model, pooled = _fixtures()
    for row in doc["records"]:
        if row["condition"] == sorted(OFFICIAL_CONDITIONS)[-1]:
            row["values"][6] += 1.0
    pooled = np.median(np.asarray([r["values"] for r in doc["records"]]), axis=0)
    result = describe_current_scaler_dispersion(doc, model, pooled)
    final = result["condition_rows"][-1]
    feature = next(f for f in final["features"] if f["feature"] == "current_kurtosis")
    assert feature["abs_condition_median_z_over_three_descriptive_only"] is True
    assert result["three_std_flag_is_descriptive_not_calibrated_outlier_threshold"] is True
    assert result["model_feature_attribution_not_physical_sensor_diagnosis"] is True


def test_duplicate_excluded_and_pooled_input_verified():
    doc, model, pooled = _fixtures()
    doc["records"][1]["duplicate_of"] = "synthetic_previous"
    doc["records"][1]["values"] = None
    pooled_unique = np.median(
        np.asarray([r["values"] for r in doc["records"]
                    if r["duplicate_of"] is None]), axis=0)
    result = describe_current_scaler_dispersion(doc, model, pooled_unique)
    assert result["source_unique_signal_pairs"] == 79
    assert result["condition_rows"][0]["unique_signal_pairs"] == 19
    with pytest.raises(ValueError, match="frozen_pooled_vector_changed"):
        describe_current_scaler_dispersion(doc, model, pooled)


def test_invalid_scaler_source_nonfinite_and_duplicate_fail_closed():
    doc, model, pooled = _fixtures()
    broken = deepcopy(model)
    broken["scale"][6] = 0.
    with pytest.raises(ValueError, match="invalid_frozen_current_scaler_contract"):
        describe_current_scaler_dispersion(doc, broken, pooled)
    malformed = deepcopy(doc)
    malformed["records"][0]["values"][6] = float("inf")
    with pytest.raises(ValueError, match="invalid_unitless_record_features"):
        describe_current_scaler_dispersion(malformed, model, pooled)
    malformed = deepcopy(doc)
    malformed["records"][0]["duplicate_of"] = "fake"
    with pytest.raises(ValueError, match="duplicate_feature_reuse"):
        describe_current_scaler_dispersion(malformed, model, pooled)
    malformed = deepcopy(doc)
    malformed["records"].pop()
    with pytest.raises(ValueError, match="incomplete_four_condition_source"):
        describe_current_scaler_dispersion(malformed, model, pooled)
    malformed = deepcopy(doc)
    malformed["records"][1]["trial"] = 1
    with pytest.raises(ValueError, match="invalid_condition_or_trial"):
        describe_current_scaler_dispersion(malformed, model, pooled)
