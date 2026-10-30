"""P2 triage: data provenance, safety precedence, repeatability and API boundaries."""
import json
import pytest
from fastapi.testclient import TestClient
from faultmate.app import app
from faultmate.diagnostics.engine import RULES, OBSERVATIONS, available_options, TriageRequest, triage
from faultmate.knowledge.repository import get_case, load_catalog

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.mark.parametrize('cid', list(RULES))
def test_every_case_stays_unconfirmed_and_grounded(cid):
    r = triage(TriageRequest(case_id=cid))
    case = get_case(cid)
    assert r['state'] == 'candidate_review'
    assert r['confirmed_fault'] is False and r['safe_to_work'] is False
    assert r['deepseek_used'] is False and r['ml_used'] is False
    assert r['external_transfer'] is False and r['stored'] is False
    assert {x['candidate'] for x in r['candidate_causes']} == {x['candidate'] for x in case['candidate_causes']}
    assert all(x['not_confirmed'] for x in r['candidate_causes'])
    assert all(x['source_ids'] for x in r['candidate_causes'])
    assert all(s['id'] in {z['id'] for z in load_catalog()['sources']} for s in r['sources'])

@pytest.mark.parametrize('cid', list(RULES))
def test_all_check_options_are_in_documented_schema(cid):
    options = available_options()['questions_by_case'][cid]
    assert set(x['id'] for x in options) == set(RULES[cid])
    assert all(x['id'] in OBSERVATIONS for x in options)
    assert len(options) > 0

@pytest.mark.parametrize('cid',list(RULES))
def test_confirmation_never_becomes_fault_even_when_all_yes(cid):
    obs = {key:'yes' for key in RULES[cid]}
    r=triage(TriageRequest(case_id=cid,observations=obs,emergency_hazard='no'))
    assert r['state']=='candidate_review'
    assert not r['confirmed_fault'] and not r['safe_to_work']
    assert all(x['not_confirmed'] for x in r['candidate_causes'])
    assert not r['next_questions']


def test_priority_based_only_on_reported_evidence_without_confidence(client):
    def ask(value):
        return client.post('/api/diagnostics/evaluate',json={
            'case_id':'CONV-001','equipment':'컨베이어',
            'observations':{'motor_rotates_log':value}
        }).json()
    yes=ask('yes'); no=ask('no'); unknown=ask('unknown')
    assert yes['candidate_causes'][0]['candidate']=='구동 전달계통 또는 벨트 장력 문제'
    assert yes['candidate_causes'][0]['review_group']=='추가 확인 우선'
    assert no['candidate_causes'][0]['candidate'] != yes['candidate_causes'][0]['candidate']
    assert unknown['candidate_causes'][0]['candidate']==no['candidate_causes'][0]['candidate']
    assert not any('probability' in entry or 'confidence' in entry for entry in yes['candidate_causes'])


def test_hazard_preempts_diagnosis(client):
    r=client.post('/api/diagnostics/evaluate',json={
        'case_id':'CONV-001','emergency_hazard':'yes',
        'observations':{'visible_jam':'yes'},
    })
    assert r.status_code==200
    x=r.json()
    assert x['state']=='safety_hold' and x['candidate_causes']==[]
    assert x['safe_to_work'] is False
    assert '즉시' in x['message']


def test_free_text_only_offers_unverified_selection(client):
    r=client.post('/api/diagnostics/evaluate',json={
        'equipment':'센서','symptom_text':'광전센서가 제품 감지 못 함'
    })
    assert r.status_code==200
    result=r.json()
    assert result['state']=='selection_required'
    assert result['candidate_causes']==[]
    assert result['suggested_cases'][0]['case_id']=='SENSOR-001'
    assert client.post('/api/diagnostics/evaluate',json={'symptom_text':'날씨가 비가 와요'}).json()['suggested_cases']==[]

@pytest.mark.parametrize('payload',[
    {'case_id':'CONV-001','equipment':'센서'},
    {'case_id':'CONV-001','observations':{'sensor_plc_mismatch_log':'yes'}},
    {'case_id':'CONV-001','observations':{'UNKNOWN_FIELD':'yes'}},
    {'observations':{'visible_jam':'yes'}},
    {'case_id':'CONV-001','observations':{'visible_jam':'maybe'}},
    {'case_id':'CONV-001','emergency_hazard':'sometimes'},
    {'case_id':'CONV-001','force_start':True},
    {'case_id':'CONV-001','symptom_text':'x'*501},
    {'case_id':'CONV-001','alarm_text':'x'*121},
    {'case_id':'CONV-001','observations':{'visible_jam':'YES'}},
])
def test_invalid_or_misleading_input_rejected(client,payload):
    r=client.post('/api/diagnostics/evaluate',json=payload)
    assert r.status_code==422, (payload,r.text)


def test_unknown_case_read_only_api_and_no_leaks(client):
    assert client.post('/api/diagnostics/evaluate',json={'case_id':'CONV-999'}).status_code==404
    assert client.post('/api/agent/execute',json={}).status_code==404
    assert client.post('/api/ml/predict',json={}).status_code==404
    assert client.post('/api/control',json={}).status_code==404
    r=client.get('/api/status').json()
    assert r['phase']=='P2' and r['deepseek_agent']=='not_connected' and r['ml_model']=='unvalidated'
    assert r['external_transfer'] is False
    assert client.get('/api/diagnostics/options').json()['cases']


def test_determinism_input_not_retained(client):
    p={'case_id':'SENSOR-001','symptom_text':'<script>alert(1)</script>',
       'observations':{'lens_contamination_seen':'yes'}}
    r1=client.post('/api/diagnostics/evaluate',json=p).json()
    other=client.post('/api/diagnostics/evaluate',json={'case_id':'MOTOR-001'}).json()
    r2=client.post('/api/diagnostics/evaluate',json=p).json()
    assert r1==r2 and other['case_id']=='MOTOR-001'
    assert '<script>' in r1['symptom_text']
    assert r1['stored'] is False


def test_html_has_live_form_and_security_response(client):
    html=client.get('/').text
    assert 'triage-form' in html and 'triage-result' in html
    assert 'DeepSeek' in html
    script=client.get('/assets/app.js').text
    assert 'renderTriageResult' in script
    assert 'textContent' in script
    assert 'innerHTML' not in script
