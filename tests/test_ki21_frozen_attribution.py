"""Synthetic arithmetic-only unit tests, NOT real Paderborn validation."""
import math

import numpy as np
import pytest

from scripts.explain_known_ki21_frozen_model import explain_frozen_logit
from scripts.extract_paderborn_unitless import FEATURE_NAMES


def test_additive_feature_contributions_reproduce_logit_and_prediction():
    n = len(FEATURE_NAMES)
    model = {
        "mean": np.zeros(n),
        "scale": np.ones(n) * 2,
        "coefs": np.arange(1, n + 1, dtype=float) / 10,
        "intercept": -0.75,
        "threshold": 0.5,
    }
    vector = np.ones(n)
    got = explain_frozen_logit(vector, model)
    expected = -0.75 + float(np.sum(vector / 2 * model["coefs"]))
    assert got["logit"] == pytest.approx(expected)
    assert math.fsum(r["signed_logit_contribution"] for r in
                     got["features_sorted_by_absolute_logit_contribution"]) + got["intercept"] == pytest.approx(expected)
    assert got["damage_model_score"] == pytest.approx(1/(1+math.exp(-expected)))
    assert got["prediction"] == "damaged"
    assert got["attribution_is_model_arithmetic_not_causal_fault_evidence"] is True


def test_negative_scores_do_not_become_safety_approval():
    n = len(FEATURE_NAMES)
    model = {
        "mean": np.zeros(n), "scale": np.ones(n),
        "coefs": np.ones(n), "intercept": -1000., "threshold": .5,
    }
    got = explain_frozen_logit(np.zeros(n), model)
    assert got["prediction"] == "healthy"
    assert got["damage_model_score"] < .5
    assert got["attribution_is_model_arithmetic_not_causal_fault_evidence"]


def test_rejects_invalid_model_scale_and_nonfinite_features():
    n = len(FEATURE_NAMES)
    model = {
        "mean": np.zeros(n), "scale": np.zeros(n),
        "coefs": np.ones(n), "intercept": 0., "threshold": .5,
    }
    with pytest.raises(ValueError, match="invalid_frozen_feature_attribution_input"):
        explain_frozen_logit(np.ones(n), model)
    model["scale"] = np.ones(n)
    vector = np.ones(n)
    vector[0] = float("nan")
    with pytest.raises(ValueError, match="invalid_frozen_feature_attribution_input"):
        explain_frozen_logit(vector, model)
