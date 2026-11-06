"""Never invoke a paid provider without separate local and per-request consent."""
from __future__ import annotations

import json
import pytest

from scripts import optional_deepseek_one_call_acceptance as live


def test_default_offline_never_reads_key_or_calls_paid_provider(monkeypatch, capsys):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SECRET_TEST_KEY_DO_NOT_ECHO")
    monkeypatch.setenv(live.LIVE_ARM_ENV, live.LIVE_ARM_VALUE)
    monkeypatch.setattr(live.agent, "review",
                        lambda *_: pytest.fail("offline must never call review/provider"))
    status = live.optional_one_live_paid_request(
        one_paid_request=False, confirm_public_demo_evidence=False)
    assert status["mode"] == "offline_preflight_only"
    assert status["paid_request_attempted"] is False
    assert status["api_key_read_or_printed"] is False
    assert status["real_deepseek_connectivity_confirmed"] is False
    assert live.main([]) == 0
    printed = capsys.readouterr().out
    assert "SECRET_TEST_KEY_DO_NOT_ECHO" not in printed
    assert "offline_preflight_only" in printed


@pytest.mark.parametrize("one_paid,confirm,armed,key,expected", [
    (True, False, True, True, "explicit_public_evidence_transmission_consent_missing"),
    (True, True, False, True, "user_local_paid_request_arming_missing"),
    (True, True, True, False, "deepseek_api_key_missing_on_user_machine"),
    (False, True, True, True, "live_request_switch_missing"),
])
def test_incomplete_paid_arming_never_invokes_agent(
    monkeypatch, one_paid, confirm, armed, key, expected
):
    monkeypatch.setenv(live.LIVE_ARM_ENV,
                       live.LIVE_ARM_VALUE if armed else "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SYNTHETIC_KEY" if key else "")
    monkeypatch.setattr(live.agent, "review",
                        lambda *_: pytest.fail("missing paid arming leaked a request"))
    with pytest.raises(ValueError, match=expected):
        live.optional_one_live_paid_request(
            one_paid_request=one_paid,
            confirm_public_demo_evidence=confirm)


def test_exactly_one_user_authorized_public_demo_follows_existing_preview(monkeypatch):
    calls = []
    monkeypatch.setenv(live.LIVE_ARM_ENV, live.LIVE_ARM_VALUE)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SYNTHETIC_FAKE_NOT_BILLABLE")

    def one_review(arg):
        calls.append(arg)
        preview = live.evidence_preview(live.ContextPreviewRequest(triage=arg.triage))
        assert arg.consent is True
        assert arg.triage.case_id == "CONV-001"
        assert arg.context_sha256 == preview["context_sha256"]
        return {
            "status": "reviewed", "external_transfer_attempted": True,
            "external_transfer_performed": True,
            "agent_review": {"candidate_causes": ["SECRET_PROVIDER_RESULT"]},
            "confirmed_fault": False, "safe_to_work": False,
        }

    monkeypatch.setattr(live.agent, "review", one_review)
    report = live.optional_one_live_paid_request(
        one_paid_request=True, confirm_public_demo_evidence=True)
    assert len(calls) == 1
    assert report["provider_response_reviewed"] is True
    assert report["paid_request_attempted"] is True
    assert report["external_transfer_performed"] is True
    assert report["safe_to_operate_equipment"] is False
    assert "SECRET_PROVIDER_RESULT" not in json.dumps(report)
    assert "SYNTHETIC_FAKE_NOT_BILLABLE" not in json.dumps(report)


def test_provider_uncertainty_is_not_misrepresented_as_no_transfer(monkeypatch):
    monkeypatch.setenv(live.LIVE_ARM_ENV, live.LIVE_ARM_VALUE)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "FAKE_NOT_PAID")
    monkeypatch.setattr(live.agent, "review", lambda *_: {
        "status": "error", "error_code": "provider_network_error",
        "external_transfer_attempted": True,
        "external_transfer_performed": None,
        "message": "USER_RAW_CASE_MUST_NOT_ECHO",
    })
    r = live.optional_one_live_paid_request(
        one_paid_request=True, confirm_public_demo_evidence=True)
    assert r["paid_request_attempted"] is True
    assert r["money_spent_may_be_nonzero"] is True
    assert r["external_transfer_performed"] is None
    assert r["no_automatic_paid_retry"] is True
    assert "USER_RAW_CASE_MUST_NOT_ECHO" not in json.dumps(r)


def test_official_model_or_endpoint_change_blocks_before_paid_request(monkeypatch):
    monkeypatch.setattr(live.agent, "ENDPOINT", "https://untrusted.example/collect")
    monkeypatch.setenv(live.LIVE_ARM_ENV, live.LIVE_ARM_VALUE)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "FAKE_KEY")
    monkeypatch.setattr(live.agent, "review",
                        lambda *_: pytest.fail("unverified provider endpoint"))
    with pytest.raises(RuntimeError, match="local_demo_or_provider_contract_unexpected"):
        live.optional_one_live_paid_request(
            one_paid_request=True, confirm_public_demo_evidence=True)


def test_cli_never_starts_paid_on_default_and_invalid_flags(monkeypatch,capsys):
    monkeypatch.setattr(live.agent, "review",
                        lambda *_: pytest.fail("unexpected call"))
    assert live.main([]) == 0
    assert live.main(["--one-paid-request"]) == 2
    output=capsys.readouterr()
    assert "explicit_public_evidence_transmission_consent_missing" in output.err
