"""P5 compatibility/safety regression retained after P6 integration."""
from pathlib import Path
from fastapi.testclient import TestClient
from faultmate.app import app

ROOT = Path(__file__).resolve().parents[1]


def test_p5_dashboard_controls_and_integration_status_exposed():
    with TestClient(app) as c:
        page = c.get('/').text
        for element in ('triage-demo','demo-banner','triage-feedback',
                        'integration-agent','integration-ml','integration-transfer',
                        'integration-panel'):
            assert f'id="{element}"' in page
        assert '<a class="nav-link" href="#knowledge-panel">' in page
        assert c.get('/api/integration/capabilities').json()['agent']['connected'] is False
        assert c.get('/api/integration/capabilities').json()['ml']['inference_enabled'] is False
        assert c.post('/api/ml/predict', json={}).status_code == 404
        assert c.post('/api/agent/execute', json={}).status_code == 404


def test_p5_client_anti_stale_and_hazard_checks_present():
    script = (ROOT/'web'/'app.js').read_text(encoding='utf-8')
    assert 'AbortController' in script
    assert 'triageRequestVersion' in script
    assert 'version !== triageRequestVersion' in script
    assert 'triageHazard.value === \'yes\'' in script
    assert 'showEmergencyHold()' in script
    assert 'demoMode' in script
    assert 'renderTriageResult' in script
    assert 'innerHTML' not in script
    assert 'textContent' in script
    assert '/api/integration/capabilities' in script
    assert '/api/agent/execute' not in script
    assert '/api/ml/predict' not in script


def test_p5_diagnostics_response_not_cachable():
    with TestClient(app) as c:
        response = c.post('/api/diagnostics/evaluate', json={
            'case_id':'CONV-001',
            'symptom_text':'private operator incident details',
            'emergency_hazard':'unknown'
        })
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store, private'
        assert response.headers['pragma'] == 'no-cache'
        assert response.json()['stored'] is False
        assert response.json()['confirmed_fault'] is False


def test_p5_emergency_api_hold_unchanged():
    with TestClient(app) as c:
        response = c.post('/api/diagnostics/evaluate', json={
            'case_id':'CONV-001',
            'emergency_hazard':'yes',
            'observations':{'visible_jam':'yes'},
        })
        assert response.status_code == 200
        body = response.json()
        assert body['state'] == 'safety_hold'
        assert body['candidate_causes'] == []
        assert not body['safe_to_work']
