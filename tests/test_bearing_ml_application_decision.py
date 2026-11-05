"""Frozen Paderborn research model application decision: fail-closed evidence tests."""
from __future__ import annotations

import json

import pytest

from faultmate.integration import agent
from faultmate.integration.ml import capabilities, load_validated_model
from scripts import decide_bearing_ml_application as decision


def test_application_decision_is_no_go_and_rule_based_app_can_continue():
    d = decision.decide_model_application()
    assert d["schema"] == "faultmate_frozen_bearing_ml_application_decision_v1"
    assert d["review_stage"] == "bearing_ml_application_no_go_review_completed"
    assert d["existing_app_can_continue_with_local_rule_based_diagnostics"] is True
    assert d["original_real_training_model_content_verified"] is True
    assert d["training_physical_bearings"] == 10
    assert d["new_independent_healthy_bearings_original_signals_verified"] == 0
    assert d["new_independent_healthy_specificity_measured"] is False
    assert d["normal_false_positive_rate_measured"] is False
    assert d["general_accuracy_measured"] is False
    assert d["production_ml_activation_allowed"] is False
    assert d["standalone_research_model_auto_approval_allowed"] is False
    assert d["bearing_model_loaded_in_app"] is False
    assert d["experimental_model_runtime_input_compatible"] is False
    assert d["source_si_unit_calibration_verified"] is False
    assert d["production_model_decision"].startswith("NO_GO")
    assert d["user_action_needed_now"] is False
    assert d["paid_deepseek_api_called"] is False
    assert d["new_ml_training_or_inference_performed"] is False
    assert load_validated_model() is None
    assert capabilities()["inference_enabled"] is False


def test_historical_eight_damaged_outcomes_are_not_fabricated_fresh_test():
    d = decision.decide_model_application()
    h = d["historical_damaged_evaluation"]
    assert h["previous_ci_run"].endswith("/41971495239")
    assert h["tested_new_physical_damaged_bearings"] == 8
    assert h["previous_ci_reported_detected"] == 7
    assert h["previous_ci_reported_missed"] == ["KI21"]
    assert h["numbers_recomputed_in_this_command"] is False
    assert d["new_independent_healthy_bearings_original_signals_verified"] == 0


def test_source_candidate_metadata_weakness_cannot_silently_approve_model(monkeypatch):
    original = decision.assess_inventory

    def fake_verified():
        r = original()
        r["new_healthy_bearings_validated"] = 5
        r["false_positive_rate_measured"] = True
        return r

    monkeypatch.setattr(decision, "assess_inventory", fake_verified)
    with pytest.raises(decision.ModelDecisionEvidenceError,
                       match="healthy_source_evidence_unjustifiably_approved"):
        decision.decide_model_application()


def test_attacker_cannot_rebrand_unapproved_research_model_by_moving_path(
        monkeypatch, tmp_path):
    fake_model = tmp_path / "bearing.json"
    fake_model.write_text('{"status":"validated","approved_for_runtime":true}')
    monkeypatch.setattr(decision, "ORIGINAL_MODEL", fake_model)
    with pytest.raises(decision.ModelDecisionEvidenceError,
                       match="frozen_model_sha256_mismatch"):
        decision.decide_model_application()


def test_frozen_test_register_cannot_be_replaced_by_newly_scored_assets(monkeypatch):
    original = decision.verified_manifest

    def fake_register():
        d = original()
        d["assets"] = [a for a in d["assets"] if a["id"] != "KI21"]
        return d

    monkeypatch.setattr(decision, "verified_manifest", fake_register)
    with pytest.raises(decision.ModelDecisionEvidenceError,
                       match="unseen_damaged_test_evidence_changed"):
        decision.decide_model_application()


def test_existing_active_ml_model_is_a_security_error_not_an_approval(monkeypatch):
    monkeypatch.setattr(decision, "load_validated_model",
                        lambda: {"status": "validated"})
    with pytest.raises(decision.ModelDecisionEvidenceError,
                       match="unexpected_existing_runtime_ml_activated"):
        decision.decide_model_application()


def test_research_model_stays_read_only_even_with_paid_api_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "FAKE_KEY_NOT_PAID_OR_REAL")
    monkeypatch.setattr(agent, "_invoke_deepseek",
                        lambda *_: pytest.fail("decision must not call provider"))
    result = decision.decide_model_application()
    assert "FAKE_KEY_NOT_PAID_OR_REAL" not in json.dumps(result)
    assert result["paid_deepseek_api_called"] is False


def test_cli_prints_json_by_default_and_never_overwrites_evidence(tmp_path,
                                                                  monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    assert decision.main([]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    d = json.loads(capsys.readouterr().out)
    assert d["production_ml_activation_allowed"] is False
    target = tmp_path / "evidence" / "decision.json"
    assert decision.main(["--out", str(target)]) == 0
    original = target.read_bytes()
    assert decision.main(["--out", str(target)]) == 2
    assert original == target.read_bytes()


def test_model_decision_not_equivalent_to_general_product_release_readiness():
    d = decision.decide_model_application()
    assert d["existing_app_can_continue_with_local_rule_based_diagnostics"]
    assert not d["production_ml_activation_allowed"]
    assert not d["experimental_model_runtime_input_compatible"]
    assert not d["general_accuracy_measured"]
    assert d["source_conditions_required"] == 4
    assert d["repeated_recordings_per_condition_required"] == 20
    assert len(d["dataset_evidence_blockers"]) >= 4
    assert len(d["source_and_product_limits"]) >= 4
