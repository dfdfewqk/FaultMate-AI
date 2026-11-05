"""Stage7 preflight contract tests: offline only, no secret, no model promotion."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from faultmate.integration import agent
from scripts import preflight_final_acceptance as preflight


def test_real_preflight_checks_local_program_without_claiming_release():
    report = preflight.collect_readiness()
    assert report["schema"] == "faultmate_final_readiness_preflight_v1"
    assert report["automatic_local_checks_passed"] is True
    assert report["checks_passed_count"] == report["checks_count"]
    assert report["checks_count"] >= 10
    assert {c["id"] for c in report["checks"]} >= {
        "existing_p72_status", "seven_local_cases",
        "hazard_never_sends_ai", "ai_preview_consent_gate",
        "unreviewed_ml_not_deployed", "real_research_model_unmodified",
        "external_healthy_evidence_honest", "loopback_only",
    }
    assert report["release_ready"] is False
    assert report["experimental_model_activated"] is False
    assert report["new_healthy_bearing_evaluation_performed"] is False
    assert report["paid_api_requests_performed"] == 0
    assert report["external_transfer_attempted"] is False
    assert report["release_gate"].startswith("BLOCKED_")
    assert len(report["external_dependencies"]) == 3
    assert len(report["only_user_can_complete"]) == 2


def test_preflight_never_invokes_provider_even_when_paid_key_is_present(
        monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "NEVER_LEAK_TEST_PAID_KEY")
    monkeypatch.setattr(agent, "_invoke_deepseek",
                        lambda *_: pytest.fail("preflight must never contact provider"))
    result = preflight.collect_readiness()
    assert result["automatic_local_checks_passed"] is True
    exported = json.dumps(result, ensure_ascii=False)
    assert "NEVER_LEAK_TEST_PAID_KEY" not in exported
    assert "Bearer" not in exported
    assert result["paid_api_requests_performed"] == 0


def test_cli_writes_only_explicit_new_report_and_never_overwrites(
        tmp_path, capsys):
    out = tmp_path / "acceptance" / "readiness.json"
    assert preflight.main(["--out", str(out)]) == 0
    assert out.is_file()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["release_ready"] is False
    old = out.read_bytes()
    assert preflight.main(["--out", str(out)]) == 2
    assert old == out.read_bytes()
    assert "refuse_to_overwrite" in capsys.readouterr().err


def test_unreviewed_or_fake_external_healthy_evidence_fails_closed(
        monkeypatch):
    original = preflight.assess_inventory

    def untrusted_evidence():
        result = original()
        result["new_healthy_bearings_validated"] = 12
        result["false_positive_rate_measured"] = True
        return result

    monkeypatch.setattr(preflight, "assess_inventory", untrusted_evidence)
    status = preflight.collect_readiness()
    by_id = {c["id"]: c for c in status["checks"]}
    assert by_id["external_healthy_evidence_honest"]["passed"] is False
    assert status["automatic_local_checks_passed"] is False
    assert status["release_ready"] is False


def test_unreviewed_ml_activation_cannot_be_silently_treated_as_ready(
        monkeypatch):
    monkeypatch.setattr(preflight, "load_validated_model",
                        lambda: {"status": "not_reviewed"})
    report = preflight.collect_readiness()
    gate = next(c for c in report["checks"]
                if c["id"] == "unreviewed_ml_not_deployed")
    assert gate["passed"] is False
    assert report["release_ready"] is False


def test_model_original_sha_tamper_blocks_preflight_without_modifying_files(
        monkeypatch, tmp_path):
    modified = tmp_path / "fake_model.json"
    modified.write_text('{"status": "validated"}', encoding="utf-8")
    monkeypatch.setattr(preflight, "ORIGINAL_MODEL", modified)
    report = preflight.collect_readiness()
    gate = next(c for c in report["checks"]
                if c["id"] == "real_research_model_unmodified")
    assert gate["passed"] is False
    assert report["release_ready"] is False


def test_no_output_file_is_created_by_default(tmp_path, monkeypatch,
                                              capsys):
    monkeypatch.chdir(tmp_path)
    before = sorted(p.name for p in Path.cwd().iterdir())
    assert preflight.main([]) == 0
    assert sorted(p.name for p in Path.cwd().iterdir()) == before
    report = json.loads(capsys.readouterr().out)
    assert report["release_ready"] is False
