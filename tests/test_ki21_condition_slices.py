"""Synthetic-only tests for read-only four-condition feature arithmetic.

No test fixture is original Paderborn sensor evidence or new validation.
"""
import copy
import math

import numpy as np
import pytest

from scripts.audit_paderborn_assets import OFFICIAL_CONDITIONS
from scripts.audit_known_ki21_conditions import compare_verified_condition_records
from scripts.extract_paderborn_unitless import FEATURE_NAMES


def _synthetic():
    n = len(FEATURE_NAMES)
    coefficients = np.array([0.6] * 6 + [-0.8] * 6, dtype=float)
    model = {
        "mean": np.zeros(n),
        "scale": np.ones(n),
        "coefs": coefficients,
        "intercept": -0.1,
        "threshold": 0.5,
    }
    doc = {"records": []}
    all_features = []
    for i, cond in enumerate(sorted(OFFICIAL_CONDITIONS)):
        for trial in range(1, 21):
            # Each condition has different synthetic feature medians. These
            # are NEVER trained or interpreted as real bearing measurements.
            values = [float(i + trial / 100.0)] * 6 + [
                float(3 - i + trial / 100.0)
            ] * 6
            doc["records"].append({
                "condition": cond, "trial": trial,
                "duplicate_of": None, "values": values,
            })
            all_features.append(values)
    pooled = np.median(np.asarray(all_features), axis=0)
    return doc, model, pooled


def test_four_condition_slices_reconstruct_exact_pooled_input():
    doc, model, pooled = _synthetic()
    out = compare_verified_condition_records(doc, model, pooled)
    assert out["original_80_record_pooled_median_reconstructed_exactly"] is True
    assert out["pooled_source_unique_signal_pairs"] == 80
    assert len(out["four_operating_conditions"]) == 4
    assert {r["condition"] for r in out["four_operating_conditions"]} == OFFICIAL_CONDITIONS
    for row in out["four_operating_conditions"]:
        assert row["original_mat_count"] == 20
        assert row["unique_signal_pairs"] == 20
        assert row["not_a_validated_per_condition_prediction"] is True
        assert row["diagnostic_condition_median_logit"] == pytest.approx(
            model["intercept"] + row["vibration_logit_contribution"]
            + row["current_logit_contribution"])
        assert len(row["largest_three_feature_contribution_differences"]) == 3
        assert row["logit_difference_from_frozen_pooled"] == pytest.approx(
            row["diagnostic_condition_median_logit"] - out["frozen_pooled_logit"])
    assert out["new_independent_data_or_accuracy_measured"] is False
    assert out["condition_only_model_scores_outside_original_training_contract"] is True
    assert out["frozen_pooled_logit"] == pytest.approx(
        model["intercept"] + out["pooled_vibration_logit_contribution"]
        + out["pooled_current_logit_contribution"])


def test_raw_signal_duplicate_excluded_without_inflating_unique_count():
    doc, model, _ = _synthetic()
    doc["records"][1]["duplicate_of"] = "synthetic_previous_record"
    doc["records"][1]["values"] = None
    unique = [r["values"] for r in doc["records"] if r["duplicate_of"] is None]
    pooled = np.median(np.asarray(unique), axis=0)
    out = compare_verified_condition_records(doc, model, pooled)
    assert out["pooled_source_unique_signal_pairs"] == 79
    first = out["four_operating_conditions"][0]
    assert first["duplicates_excluded"] == 1
    assert first["unique_signal_pairs"] == 19


def test_pooled_feature_mismatch_and_duplicate_forgery_fail_closed():
    doc, model, pooled = _synthetic()
    wrong = pooled.copy()
    wrong[0] += 0.05
    with pytest.raises(ValueError, match="condition_reaggregation_differs"):
        compare_verified_condition_records(doc, model, wrong)
    doc["records"][0]["duplicate_of"] = "another_record"
    with pytest.raises(ValueError, match="duplicate_must_not_contribute"):
        compare_verified_condition_records(doc, model, pooled)


def test_incomplete_conditions_bad_features_and_repeated_trials_fail_closed():
    doc, model, pooled = _synthetic()
    incomplete = copy.deepcopy(doc)
    incomplete["records"].pop()
    with pytest.raises(ValueError, match="incomplete_four_condition"):
        compare_verified_condition_records(incomplete, model, pooled)
    nonfinite = copy.deepcopy(doc)
    nonfinite["records"][0]["values"][2] = float("inf")
    with pytest.raises(ValueError, match="invalid_condition_feature_vector"):
        compare_verified_condition_records(nonfinite, model, pooled)
    repeated = copy.deepcopy(doc)
    repeated["records"][1]["trial"] = repeated["records"][0]["trial"]
    with pytest.raises(ValueError, match="invalid_condition_trial"):
        compare_verified_condition_records(repeated, model, pooled)
