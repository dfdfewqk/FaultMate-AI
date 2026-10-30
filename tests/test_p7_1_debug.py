"""P7.1 fixes: parser fail-closed, release status, AI/ML stale request protections."""
from fastapi.testclient import TestClient
from faultmate.app import app
from faultmate.integration.ml import parse_feature_csv
import pytest


def test_large_csv_field_no_longer_crashes_backend():
    body = ('asset_id,trial_id,source_id,vibration_rms_m_s2,vibration_peak_m_s2,current_rms_a\n'
            + 'x' * 150_000 + ',t,s,1,2,3\n').encode()
    with TestClient(app) as c:
        response = c.post('/api/ml/inspect', content=body,
                          headers={'content-type': 'text/csv'})
    assert response.status_code == 200
    assert response.json()['status'] == 'unsupported_input'
    assert response.json()['inference_performed'] is False
    assert response.json()['confirmed_fault'] is False


def test_malformed_csv_training_input_is_rejected_with_value_error():
    body = ('asset_id,trial_id,source_id,vibration_rms_m_s2,vibration_peak_m_s2,current_rms_a,label,label_provenance,license\n'
            + 'x' * 150_000 + ',t,s,1,2,3,healthy,fixture,test\n').encode()
    with pytest.raises(ValueError,match='malformed_csv_row'):
        parse_feature_csv(body,training=True)


def test_status_reflects_available_code_not_claimed_trained_model():
    with TestClient(app) as c:
        status = c.get('/api/status').json()
        caps = c.get('/api/integration/capabilities').json()
    assert status['ui_release'] == 'P7.2-Final'
    assert status['phase'] == 'P2' # Legacy rule contract preserved.
    assert status['ml_model'] == 'unvalidated'
    assert caps['ml']['inference_enabled'] is False
    assert status['external_transfer'] is False


def test_safety_and_diagnostic_endpoints_unchanged():
    with TestClient(app) as c:
        regular = c.post('/api/diagnostics/evaluate',json={'case_id':'CONV-001'}).json()
        hold = c.post('/api/diagnostics/evaluate',json={
            'case_id':'CONV-001','emergency_hazard':'yes'}).json()
    assert regular['state'] == 'candidate_review'
    assert hold['state'] == 'safety_hold' and hold['candidate_causes'] == []


def test_large_csv_header_no_longer_crashes_backend():
    body = ('x' * 150_000 + ',asset_id,trial_id,source_id,vibration_rms_m_s2,vibration_peak_m_s2,current_rms_a\n'
            'other,bearing1,t,s,1,2,3\n').encode()
    with TestClient(app) as c:
        response = c.post('/api/ml/inspect',content=body,headers={'content-type':'text/csv'})
    assert response.status_code == 200
    assert response.json()['status'] == 'unsupported_input'
    assert response.json()['inference_performed'] is False
