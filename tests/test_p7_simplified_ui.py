"""Regression: streamlined UI keeps safety and advanced functionality intact."""
from pathlib import Path
from fastapi.testclient import TestClient
from faultmate.app import app

ROOT = Path(__file__).resolve().parents[1]

def test_first_screen_is_operator_focused_not_development_dashboard():
    with TestClient(app) as client:
        body = client.get('/').text
        assert '설비 고장 진단' in body
        assert '<div class="stats">' not in body
        assert '첫 번째 검증 시나리오' not in body
        assert '개발 진행 단계' not in body
        assert body.index('id="diagnostic-panel"') < body.index('id="integration-panel"')
        assert body.index('id="diagnostic-panel"') < body.index('id="knowledge-panel"')

def test_essential_risks_and_original_control_ids_remain_available():
    with TestClient(app) as client:
        body = client.get('/').text
        for element in ('triage-equipment','triage-case','triage-hazard','triage-submit',
                        'triage-checks','triage-result','triage-symptom','triage-model','triage-alarm',
                        'agent-consent','agent-run','agent-preview','ml-upload','ml-run',
                        'knowledge-list','knowledge-detail'):
            assert f'id="{element}"' in body
        assert '화재·연기·감전 우려·사람 끼임' in body
        assert '<details class="optional-fields" id="triage-more">' in body
        assert '<details class="panel expand-panel" id="integration-panel">' in body
        assert '<details class="panel expand-panel" id="knowledge-panel">' in body
        assert 'id="triage-hazard"' in body

def test_advanced_items_accessible_by_sidebar_without_auto_activating():
    js = (ROOT/'web'/'app.js').read_text(encoding='utf-8')
    assert 'target.open = true' in js
    assert 'location.hash' in js
    assert "agentConsent.checked = false" in js
    assert 'showEmergencyHold()' in js
