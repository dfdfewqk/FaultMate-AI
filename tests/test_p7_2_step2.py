"""P7.2 step 2 safety-information UI contract (no new server API)."""
from pathlib import Path
from faultmate.diagnostics.engine import TriageRequest, triage

ROOT = Path(__file__).resolve().parents[1]


def test_safety_check_precedes_case_recommendations_and_selection():
    html = (ROOT / 'web/index.html').read_text(encoding='utf-8')
    assert html.index('id="triage-hazard"') < html.index('id="triage-suggestion-list"')
    assert html.index('id="triage-hazard"') < html.index('id="triage-case"')
    assert 'id="hazard-status"' in html and 'aria-live="polite"' in html


def test_ui_distinguishes_unknown_no_yes_and_reset():
    js = (ROOT / 'web/app.js').read_text(encoding='utf-8')
    assert 'function updateHazardStatus()' in js
    assert '안전 상태 미확인' in js
    assert '안전하다는 인증이나 정비 작업 허가가 아닙니다' in js
    assert '원인 후보 검토와 AI·ML 분석을 중단합니다' in js
    assert "triageForm.reset();\n    updateHazardStatus();" in js


def test_engine_never_treats_unknown_as_emergency_yes():
    # Existing engine allows read-only triage with unknown, but stops on affirmative hazard.
    unknown = triage(TriageRequest(equipment='컨베이어', case_id='CONV-001', emergency_hazard='unknown'))
    danger = triage(TriageRequest(equipment='컨베이어', case_id='CONV-001', emergency_hazard='yes'))
    assert unknown['state'] != 'safety_hold'
    assert danger['state'] == 'safety_hold'
    assert not danger.get('candidate_causes')
