"""P7.2 stage 4 regression contract for optional lazy loading."""
from pathlib import Path
from fastapi.testclient import TestClient
from faultmate.app import app

ROOT = Path(__file__).resolve().parents[1]

def test_lazy_knowledge_request_does_not_gate_diagnostics():
    js = (ROOT / 'web/app.js').read_text(encoding='utf-8')
    assert "knowledgePanel.addEventListener('toggle'" in js
    assert 'void ensureKnowledgeLoaded()' in js
    assert "if (knowledgeLoaded) return;" in js
    assert "knowledgeLoadPromise" in js
    assert 'lastRenderedFilter !== filter.value' in js
    assert "const status = await request('/api/status');" in js
    assert "const caps = await request('/api/integration/capabilities');" in js
    assert 'void (async () => {' in js

def test_local_endpoint_and_phase_compatibility_preserved():
    c = TestClient(app)
    s = c.get('/api/status').json()
    assert s['ui_release'] == 'P7.2-Final'
    assert s['phase'] == 'P2'
    assert len(c.get('/api/diagnostics/options').json()['cases']) == 7
