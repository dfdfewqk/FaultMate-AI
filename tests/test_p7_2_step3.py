"""Operator-first result screen: disclosure keeps all evidence and safety visible."""
from pathlib import Path
from faultmate.diagnostics.engine import TriageRequest, triage

ROOT=Path(__file__).resolve().parents[1]


def test_step3_disclosure_is_keyboard_accessible_and_safe():
    js=(ROOT/'web/app.js').read_text(encoding='utf-8')
    css=(ROOT/'web/style.css').read_text(encoding='utf-8')
    assert "details.id = 'triage-result-details'" in js
    assert "add(details, 'summary'" in js
    assert 'result-details>summary:focus-visible' in css
    assert "add(triageResult, 'p', data.safety_gate, 'result-hold')" in js
    assert "add(triageResult, 'p', data.stop_escalation, 'result-note')" in js
    assert "add(details, 'p', data.notice, 'result-note')" in js
    assert 'addSafeSourceLink(details, s' in js
    assert "addList(details, questions)" in js


def test_original_engine_candidates_questions_and_sources_remain_unmodified():
    data=triage(TriageRequest(equipment='컨베이어',case_id='CONV-001',emergency_hazard='unknown'))
    assert data['state']=='candidate_review'
    assert len(data['candidate_causes'])==3
    assert len(data['sources'])>=1
    assert len(data['next_questions'])+len(data['additional_information_questions'])>=3
    assert data['safe_to_work'] is False
    danger=triage(TriageRequest(equipment='컨베이어',case_id='CONV-001',emergency_hazard='yes'))
    assert danger['state']=='safety_hold' and danger['candidate_causes']==[]
