"""Offline safety tests, with synthetic proposals only; no new bearing test."""
from copy import deepcopy
import json

import pytest

from scripts.audit_independent_bearing_preflight import (
    PLAN_PATH, IndependentSourceGateError, audit_current_readiness,
    inspect_prospective_draft,
)


def _draft():
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _proposal(asset, fingerprint="a" * 64, label="healthy"):
    return {
        "physical_asset_id": asset,
        "source_id": "synthetic-not-a-real-source",
        "primary_label": label,
        "proposed_original_archive_sha256": fingerprint,
    }


def test_actual_review_has_zero_new_bearings_and_all_four_sources_blocked():
    result = audit_current_readiness()
    assert result["status"] == "NO_GO_NO_NEW_PROSPECTIVE_PHYSICAL_BEARING_COHORT"
    assert result["original_frozen_model_verified"] is True
    assert result["paderborn_all_six_healthy_previously_opened"] is True
    assert result["existing_public_candidate_sources_reviewed"] == 4
    assert result["new_independent_normal_bearings_verified"] == 0
    assert result["new_independent_damaged_bearings_verified"] == 0
    assert result["new_independent_specificity_or_accuracy_measured"] is False
    assert result["production_ml_activation_allowed"] is False
    assert result["model_retrained_or_scored"] is False
    assert result["paid_api_called"] is False
    assert len(result["missing_preconditions"]) >= 8
    assert not any(result["readiness_checks"].values())
    names = {r["source_id"] for r in result["source_rejections"]}
    assert names == {
        "paderborn_healthy_reuse", "kaist_varying_load",
        "kaist_varying_speed", "phm24_bjtu_rao_bogie",
    }
    for src in result["source_rejections"]:
        assert src["reasons"]


@pytest.mark.parametrize("known", ["K001", "K006", "KI18", "KI21", "KA15", "KB27"])
def test_historical_physical_bearings_cannot_reenter_a_new_test(known):
    plan = _draft()
    plan["physical_asset_proposals"] = [_proposal(known)]
    with pytest.raises(IndependentSourceGateError, match="historical_or_duplicate"):
        inspect_prospective_draft(plan)


def test_duplicate_physical_ids_and_duplicate_raw_hash_claim_fail_closed():
    plan = _draft()
    plan["physical_asset_proposals"] = [
        _proposal("NEW-A", "a" * 64),
        _proposal("NEW-A", "b" * 64, label="damaged"),
    ]
    with pytest.raises(IndependentSourceGateError, match="historical_or_duplicate"):
        inspect_prospective_draft(plan)
    plan["physical_asset_proposals"][1]["physical_asset_id"] = "NEW-B"
    plan["physical_asset_proposals"][1]["proposed_original_archive_sha256"] = "a" * 64
    with pytest.raises(IndependentSourceGateError, match="historical_or_duplicate"):
        inspect_prospective_draft(plan)


def test_proposals_are_never_verified_just_because_identifiers_look_valid():
    plan = _draft()
    plan["physical_asset_proposals"] = [
        _proposal("NEW-A", "a" * 64),
        _proposal("NEW-B", "b" * 64, label="damaged"),
    ]
    for key in [
        "source_license_for_proposed_use_verified",
        "four_official_conditions_20_mat_each_bearing_verified",
        "paired_64000hz_vibration_and_motor_current_original_signals_verified",
        "raw_source_archive_and_signal_sha256_verified",
        "zero_reuse_of_previously_opened_physical_bearings_and_signal_hashes_verified",
        "protocol_committed_prior_to_any_new_test_source",
    ]:
        plan[key] = True
    plan["proposed_source_id"] = "synthetic-not-a-real-source"
    plan["independent_physical_healthy_bearing_count_verified"] = 1
    plan["independent_physical_damaged_bearing_count_verified"] = 1
    plan["planned_minimum_healthy_bearings_before_data"] = 1
    plan["planned_minimum_damaged_bearings_before_data"] = 1
    plan["primary_bearing_level_metric_frozen_before_data"] = "synthetic_specificity"
    plan["confidence_interval_method_frozen_before_data"] = "synthetic_method"
    plan["minimum_acceptable_result_frozen_before_data"] = "synthetic_acceptance"
    result = inspect_prospective_draft(plan)
    assert result["proposed_asset_metadata_rows"] == 2
    assert result["metadata_proposals_never_verified_raw_evidence"] is True
    assert result["production_ml_activation_allowed"] is False
    assert result["model_retrained_or_scored"] is False
    assert result["new_independent_normal_bearings_verified"] == 0
    assert result["status"].startswith("NO_GO")


def test_no_change_to_frozen_model_and_past_results_is_allowed():
    plan = _draft()
    altered = deepcopy(plan)
    altered["frozen_research_model_sha256"] = "0" * 64
    with pytest.raises(IndependentSourceGateError, match="prospective_plan_cannot"):
        inspect_prospective_draft(altered)
    altered = deepcopy(plan)
    altered["preexisting_experiment_results_seen"] = False
    with pytest.raises(IndependentSourceGateError, match="prospective_plan_cannot"):
        inspect_prospective_draft(altered)
    altered = deepcopy(plan)
    altered["status"] = "prospectively_blind_and_validated"
    with pytest.raises(IndependentSourceGateError, match="prospective_plan_cannot"):
        inspect_prospective_draft(altered)
    altered = deepcopy(plan)
    altered["prospective_test_approved_to_run"] = True
    with pytest.raises(IndependentSourceGateError, match="draft_cannot_claim"):
        inspect_prospective_draft(altered)


def test_corrupt_proposed_asset_metadata_denied():
    plan = _draft()
    plan["physical_asset_proposals"] = [
        _proposal("NEW-A", "bad-hash", label="healthy")
    ]
    with pytest.raises(IndependentSourceGateError, match="invalid_proposed_asset"):
        inspect_prospective_draft(plan)
    plan["physical_asset_proposals"][0]["proposed_original_archive_sha256"] = "a" * 64
    plan["physical_asset_proposals"][0]["primary_label"] = "unknown"
    with pytest.raises(IndependentSourceGateError, match="invalid_proposed_asset"):
        inspect_prospective_draft(plan)
