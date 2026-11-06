"""Safe synthetic contract tests; synthetic bearing scores are NOT real evidence."""
from collections import Counter
import json

import pytest

from scripts import evaluate_paderborn_retro_normal_lobo as retro
from scripts.audit_paderborn_assets import SourceAuditError


def synthetic_retrospective_rows():
    rows = []
    assets = sorted(retro.EXPECTED_DEVELOPMENT | retro.EXPECTED_PRIOR_TEST)
    for i, asset in enumerate(assets):
        label = "healthy" if asset.startswith("K") and not asset.startswith(("KA", "KB", "KI")) else "damaged"
        for trial in range(76 if asset == "KA04" else 80):
            # Deliberately distinguish classes using data generated in this test.
            # The values are not from real Paderborn signals.
            midpoint = 0.3 if label == "healthy" else 3.0
            rows.append({
                "asset_id": asset, "label": label,
                "recording": f"{asset}_{trial}",
                "condition": "N15_M07_F10",
                "features": [
                    midpoint + 0.005 * trial + 0.01 * i + 0.0003 * k
                    for k in range(12)
                ],
            })
    return rows


def test_group_population_has_12_physical_bearings_not_956_independent_assets():
    rows = synthetic_retrospective_rows()
    assert len(rows) == 956
    assert Counter(r["label"] for r in rows) == {"healthy": 480, "damaged": 476}
    out = retro.retrospective_group_lobo(rows)
    assert out["metrics"]["physical_bearings"] == 12
    assert len(out["fold_predictions"]) == 12
    assert out["metrics"]["confusion_matrix_labels"] == ("healthy", "damaged")
    assert out["candidate_selected_using_historical_development_outcomes"] is True
    assert out["fixed_non_tuned_classification_threshold"] == 0.5
    assert out["model_refit_each_group_fold"] is True
    for k in ("descriptive_healthy_specificity_wilson95",
              "descriptive_damage_sensitivity_wilson95"):
        lower, upper = out[k]
        assert 0 <= lower <= upper <= 1


@pytest.mark.parametrize("mutate", [
    lambda rows: rows.pop(),  # cannot convert 955 records into 956 physical assets
    lambda rows: rows.append(rows[0].copy()),  # duplicate recording
    lambda rows: rows.__setitem__(0, {**rows[0], "label": "damaged"}),  # mixed physical label
    lambda rows: rows.__setitem__(0, {**rows[0], "asset_id": "K999"}),  # unapproved asset
])
def test_invalid_group_membership_fails_closed(mutate):
    rows = synthetic_retrospective_rows()
    mutate(rows)
    with pytest.raises(SourceAuditError, match="population_or_groups_invalid"):
        retro.retrospective_group_lobo(rows)


@pytest.mark.parametrize(("good", "all_trials"), [(0, 6), (3, 6), (6, 6)])
def test_wilson_interval_is_well_bounded(good, all_trials):
    a, b = retro.wilson_interval(good, all_trials)
    assert 0 <= a <= good / all_trials <= b <= 1
    if good in (0, all_trials):
        assert b - a > 0.1


@pytest.mark.parametrize(("num", "den"), [(-1, 6), (7, 6), (0, 0), (True, 6)])
def test_invalid_statistics_denied(num, den):
    with pytest.raises(ValueError, match="invalid_bernoulli_counts"):
        retro.wilson_interval(num, den)


def test_prior_baseline_bytes_must_be_exactly_hash_pinned(tmp_path):
    baseline = tmp_path / "real_unitless_evaluation.json"
    baseline.write_text(json.dumps({
        "status": "real_source_experimental_training_finished_no_runtime_approval",
        "ml_model_approved": False,
    }), encoding="utf-8")
    with pytest.raises(SourceAuditError, match="prior_real_model_evaluation_sha_mismatch"):
        retro.verify_previous_evidence(tmp_path / "features", tmp_path / "audits", baseline)


def test_never_alters_existing_output_file(tmp_path):
    dest = tmp_path / "old_evaluation.json"
    dest.write_text("DO_NOT_OVERWRITE", encoding="utf-8")
    # Running without old real files must block, and it must not touch existing output.
    ret = retro.main([
        "--features-dir", str(tmp_path),
        "--audits-dir", str(tmp_path),
        "--previous-report", str(tmp_path / "missing.json"),
        "--out", str(dest),
    ])
    assert ret == 2
    assert dest.read_text(encoding="utf-8") == "DO_NOT_OVERWRITE"
