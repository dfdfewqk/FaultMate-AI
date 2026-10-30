"""P5 UI safety and integration regression. Browser interaction in browser_smoke.py."""
from fastapi.testclient import TestClient
from faultmate.app import app


def test_frontend_uses_live_status_not_fake_connection():
    with TestClient(app) as c:
        html = c.get('/').text
        js = c.get('/assets/app.js').text
        assert 'id="agent-status"' in html
        assert 'id="integration-ml"' in html
        assert 'id="triage-submit" disabled' in html
        assert "request('/api/integration/capabilities')" in js
        assert 'caps.ml?.inference_enabled === true' in js


def test_frontend_protects_pending_response_and_errors():
    with TestClient(app) as c:
        script = c.get('/assets/app.js').text
        assert 'triageRequestVersion' in script
        assert 'activeTriageController.abort()' in script
        assert "triageHazard.value === 'yes'" in script
        assert 'syncTriageButton()' in script
        assert 'version !== triageRequestVersion' in script
        assert 'renderTriageResult(result, reviewedDemo, reviewedPayload)' in script
        assert 'innerHTML' not in script


def test_knowledge_switch_discards_stale_responses():
    with TestClient(app) as c:
        script = c.get('/assets/app.js').text
        assert 'caseViewVersion' in script and 'listViewVersion' in script
        assert 'version !== caseViewVersion' in script
        assert 'version !== listViewVersion' in script
        assert 'aria-pressed' in script
        assert "url.protocol !== 'https:'" in script


def test_ui_links_use_real_section_targets():
    with TestClient(app) as c:
        html = c.get('/').text
        assert 'href="#diagnostic-panel"' in html
        assert 'href="#knowledge-panel"' in html
        assert 'id="diagnostic-panel"' in html
        assert 'id="knowledge-panel"' in html


def test_p2_diagnostic_and_p3_contract_still_work():
    with TestClient(app) as c:
        result = c.post('/api/diagnostics/evaluate', json={
            'case_id': 'CONV-001', 'equipment': '컨베이어',
            'observations': {'visible_jam': 'yes'},
        })
        assert result.status_code == 200
        assert result.json()['state'] == 'candidate_review'
        assert result.json()['confirmed_fault'] is False
        hold = c.post('/api/diagnostics/evaluate', json={
            'case_id': 'CONV-001', 'emergency_hazard': 'yes',
        })
        assert hold.status_code == 200 and hold.json()['state'] == 'safety_hold'
        agent = c.get('/api/integration/capabilities').json()
        assert agent['agent']['connected'] is False
        assert agent['ml']['inference_enabled'] is False
