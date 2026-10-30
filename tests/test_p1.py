"""P1 tests: evidence provenance, read-only API, safe-by-design catalogue."""
import copy
from fastapi.testclient import TestClient
import pytest
from faultmate.app import app
from faultmate.knowledge.repository import load_catalog,validate_catalog,case_summaries,get_case

def test_catalog_schema_and_provenance():
    assert validate_catalog(load_catalog()) is True
    for case in load_catalog()['cases']:
        assert case['case_status']=='illustrative_evidence_map'
        assert case['alarm_code'] is None
        assert all(c['not_confirmed'] is True for c in case['candidate_causes'])

def test_catalog_rejects_unverified_alarm_or_claim():
    c=copy.deepcopy(load_catalog()); c['cases'][0]['alarm_code']='F001'
    with pytest.raises(ValueError): validate_catalog(c)
    c=copy.deepcopy(load_catalog());c['cases'][0]['candidate_causes'][0]['not_confirmed']=False
    with pytest.raises(ValueError): validate_catalog(c)

def test_catalog_rejects_invalid_source():
    c=copy.deepcopy(load_catalog()); c['cases'][0]['candidate_causes'][0]['source_ids']=['UNKNOWN']
    with pytest.raises(ValueError): validate_catalog(c)
    c=copy.deepcopy(load_catalog()); c['sources'][0]['url']='file:///tmp/test'
    with pytest.raises(ValueError): validate_catalog(c)

def test_catalog_counts_and_filter():
    assert len(case_summaries()) == 7
    assert len(case_summaries('센서')) == 2
    assert get_case('CONV-001')['equipment']=='컨베이어'
    assert get_case('NOT-FOUND') is None

def test_knowledge_api_contract():
    with TestClient(app) as client:
        status=client.get('/api/status').json()
        assert status['phase']=='P2'
        assert status['deepseek_agent']=='not_connected'
        assert status['external_transfer'] is False
        ov=client.get('/api/knowledge/overview').json()
        assert (ov['case_count'],ov['source_count'])==(7,8)
        assert ov['diagnosis_available'] is True
        assert ov['agent_ml_owner']=='Antigravity'
        assert len(client.get('/api/knowledge/sources').json()['sources'])==8
        assert len(client.get('/api/knowledge/cases').json()['cases'])==7
        assert len(client.get('/api/knowledge/cases?equipment=모터').json()['cases'])==2
        assert client.get('/api/knowledge/cases?equipment=PLC').status_code==422
        assert client.get('/api/knowledge/cases/NONE').status_code==404
        c=client.get('/api/knowledge/cases/CONV-001').json()['case']
        assert c['candidate_causes'][0]['not_confirmed'] is True

def test_p1_not_diagnostic_nor_external():
    with TestClient(app) as client:
        for path in ('/api/diagnose','/api/agent/execute','/api/ml/predict','/api/control','/api/analyze'):
            assert client.post(path,json={'text':'test'}).status_code==404
        assert client.get('/').status_code==200
        body=client.get('/').text
        assert '근거 자료실' in body
        assert 'knowledge-list' in body
