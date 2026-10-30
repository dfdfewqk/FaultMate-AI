"""P3 handoff tests. Intentionally NO DeepSeek or ML network integration."""
import pytest
from fastapi.testclient import TestClient
from faultmate.app import app
from faultmate.diagnostics.engine import RULES
from faultmate.integration.context import ContextPreviewRequest, evidence_preview
from faultmate.knowledge.repository import get_case, load_catalog


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def post(client, **triage):
    return client.post('/api/integration/evidence-preview', json={'triage': triage})


def test_capabilities_are_explicitly_unconnected(client):
    response = client.get('/api/integration/capabilities')
    assert response.status_code == 200
    body = response.json()
    assert body['owner'] == {'agent':'ChatGPT_P6_backend','ml':'ChatGPT_P6_backend'}
    assert body['agent']['connected'] is False
    assert body['agent']['external_transfer'] is False
    assert body['ml']['inference_enabled'] is False
    assert not any(body['hard_limits'].values())


@pytest.mark.parametrize('case_id', list(RULES))
def test_all_cases_preview_grounded_and_unconfirmed(client, case_id):
    response = post(client, case_id=case_id)
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store, private'
    body = response.json()
    assert body['allowed_for_agent_reasoning'] is True
    assert body['state'] == 'candidate_review'
    for key in ('external_transfer_performed', 'user_consent_captured',
                'ml_inference_performed', 'confirmed_fault', 'safe_to_work', 'stored'):
        assert body[key] is False
    payload = body['context']
    expected = get_case(case_id)
    assert payload['case_id'] == case_id
    assert {c['candidate'] for c in payload['candidate_causes']} == {
        c['candidate'] for c in expected['candidate_causes']
    }
    assert all(c['not_confirmed'] for c in payload['candidate_causes'])
    source_ids = {s['id'] for s in payload['sources']}
    assert source_ids <= {s['id'] for s in load_catalog()['sources']}
    assert {ref for c in payload['candidate_causes'] for ref in c['source_ids']} == source_ids
    assert all(s['limit'] and s['evidence_scope'] for s in payload['sources'])
    assert all(c['review_group'] in ('추가 확인 우선', '일반 검토 후보') for c in payload['candidate_causes'])


def test_free_text_and_model_details_never_leak_to_preview(client):
    secret='PERSON_NAME_PRIVATE_2026'
    response=post(client,case_id='CONV-001',symptom_text='x'+secret,
                  alarm_text='A1'+secret,model_name='ABC-'+secret,
                  observations={'visible_jam':'yes'})
    assert response.status_code == 200
    assert secret not in response.text
    assert response.json()['context']['observations'] == {'visible_jam':'yes'}


def test_safety_hold_blocks_context_even_with_matching_case(client):
    response=post(client,case_id='CONV-001',emergency_hazard='yes',
                  observations={'visible_jam':'yes'},symptom_text='SENSITIVE_INCIDENT')
    assert response.status_code == 200
    body=response.json()
    assert body['state'] == 'safety_hold'
    assert body['context'] is None and body['allowed_for_agent_reasoning'] is False
    assert 'SENSITIVE_INCIDENT' not in response.text


def test_missing_case_never_auto_selects(client):
    body=post(client,equipment='센서',symptom_text='광전센서 감지 못 함').json()
    assert body['state']=='selection_required'
    assert body['context'] is None
    assert body['allowed_for_agent_reasoning'] is False


@pytest.mark.parametrize('triage,code',[
    ({'case_id':'CONV-999'},404),
    ({'case_id':'CONV-001','equipment':'센서'},422),
    ({'case_id':'CONV-001','observations':{'nonexistent':'yes'}},422),
    ({'case_id':'CONV-001','observations':{'lens_contamination_seen':'yes'}},422),
    ({'case_id':'CONV-001','observations':{'visible_jam':'maybe'}},422),
    ({'case_id':'CONV-001','force_control':True},422),
])
def test_invalid_integration_input_rejected(client,triage,code):
    assert post(client,**triage).status_code==code


def test_extra_fields_and_model_override_rejected(client):
    assert client.post('/api/integration/evidence-preview',json={
        'triage':{'case_id':'CONV-001'},'confirmed_fault':True
    }).status_code==422
    assert client.post('/api/integration/evidence-preview',json={
        'triage':{'case_id':'CONV-001'},'external_transfer_consent':True
    }).status_code==422
    assert client.post('/api/agent/execute',json={'prompt':'run machine'}).status_code==404
    assert client.post('/api/ml/predict',json={'case_id':'CONV-001'}).status_code==404
    assert client.post('/api/control',json={'machine':'A','command':'start'}).status_code==404


def test_preview_is_deterministic_and_does_not_modify_p2(client):
    triage={'case_id':'SENSOR-001','observations':{'lens_contamination_seen':'yes'}}
    before=client.post('/api/diagnostics/evaluate',json=triage).json()
    p1=post(client,**triage).json()
    p2=post(client,**triage).json()
    after=client.post('/api/diagnostics/evaluate',json=triage).json()
    assert p1==p2 and before==after
    assert before['confirmed_fault'] is False and p1['confirmed_fault'] is False
