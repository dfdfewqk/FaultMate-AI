"""P7.2-1: symptom-to-case suggestions only, no automated diagnosis."""
from pathlib import Path
from fastapi.testclient import TestClient
from faultmate.app import app
from faultmate.diagnostics.engine import suggestions

ROOT = Path(__file__).resolve().parents[1]

def test_matching_is_scoped_to_selected_equipment():
    matches = suggestions("모터 소리만 나고 벨트가 움직이지 않음", "컨베이어")
    assert [m["case_id"] for m in matches] == ["CONV-001"]
    assert all(m["equipment"] == "컨베이어" for m in matches)

def test_unknown_symptom_cannot_be_misrepresented_as_a_match():
    assert suggestions("윤활유 냄새가 평소와 다릅니다", "모터") == []

def test_selection_required_is_not_a_diagnosis():
    with TestClient(app) as client:
        response = client.post('/api/diagnostics/evaluate', json={
            "equipment": "컨베이어", "symptom_text": "모터에서 소리가 나는데 벨트가 움직이지 않음",
            "emergency_hazard": "unknown", "observations": {}, "case_id": None
        })
        assert response.status_code == 200
        body = response.json()
        assert body['state'] == 'selection_required'
        assert body['suggested_cases'][0]['case_id'] == 'CONV-001'
        assert body['candidate_causes'] == []
        assert body['confirmed_fault'] is False
        assert body['deepseek_used'] is False and body['ml_used'] is False
        assert body['external_transfer'] is False and body['stored'] is False

def test_emergency_preempts_suggestions():
    with TestClient(app) as client:
        body = client.post('/api/diagnostics/evaluate', json={
            'equipment':'컨베이어', 'symptom_text':'모터 소리 벨트가 움직이지',
            'case_id':None, 'emergency_hazard':'yes', 'observations':{}
        }).json()
        assert body['state'] == 'safety_hold'
        assert body['suggested_cases'] == []
        assert body['candidate_causes'] == []

def test_invalid_equipment_cannot_trigger_cross_category_suggestions():
    with TestClient(app) as client:
        r = client.post('/api/diagnostics/evaluate', json={
            'equipment':'펌프', 'symptom_text':'모터 소리', 'case_id':None})
        assert r.status_code == 422

def test_page_exposes_primary_symptoms_before_choice_without_new_external_service():
    html = (ROOT/'web'/'index.html').read_text(encoding='utf8')
    js = (ROOT/'web'/'app.js').read_text(encoding='utf8')
    assert html.index('id="triage-equipment"') < html.index('id="triage-symptom"') < html.index('id="triage-case"')
    assert html.count('id="triage-symptom"') == 1
    assert 'id="triage-suggestion-list"' in html
    assert 'id="triage-case" required' in html
    assert "'/api/diagnostics/evaluate'" in js
    assert 'dataset.suggestCase' in js
    assert 'case_id: null' in js
    assert 'triageHazard.value === \'yes\'' in js
    assert 'innerHTML' not in js
