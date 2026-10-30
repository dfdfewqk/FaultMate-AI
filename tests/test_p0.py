"""P0 tests are purposely independent from DeepSeek and the old MicroLoss repo."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from faultmate.app import app
from scripts.start import choose_port, load_app

ROOT = Path(__file__).resolve().parents[1]

def test_status_no_diagnosis_or_external_calls():
    with TestClient(app) as c:
        r = c.get('/api/status')
        assert r.status_code == 200
        o = r.json()
        assert o['app'] == 'FaultMate AI'
        assert o['diagnostic_engine'] == 'deterministic_rules_unverified'
        assert o['deepseek_agent'] == 'not_connected'
        assert o['external_transfer'] is False
        assert 'api_key' not in o

def test_no_microloss_endpoints():
    with TestClient(app) as c:
        assert c.get('/api/demo-predict').status_code == 404
        assert c.get('/api/demo').status_code == 404
        assert c.get('/api/agent/status').status_code == 404
        assert c.post('/api/analyze').status_code == 404

def test_static_assets_and_brand():
    with TestClient(app) as c:
        r = c.get('/')
        assert r.status_code == 200
        assert 'FaultMate AI' in r.text
        assert '실제 원인을 확정하거나' in r.text
        assert c.get('/assets/style.css').status_code == 200
        assert c.get('/assets/app.js').status_code == 200

def test_scope_only_planned_content():
    with TestClient(app) as c:
        o = c.get('/api/scope').json()
        assert o['target'] == ['컨베이어','모터','센서']
        assert o['example']['status'] == 'unverified_example'
        assert '설비 원격 제어' in o['prohibited']

def test_invalid_ports_rejected():
    for port in (0,-1,65536):
        try: choose_port(port)
        except ValueError: pass
        else: assert False, 'invalid port was accepted'

def test_entrypoint_import_from_elsewhere():
    code = "from pathlib import Path; import sys;sys.path.insert(0,sys.argv[1]);from scripts.start import load_app;app=load_app();print(app.title)"
    p = subprocess.run([sys.executable,'-c',code,str(ROOT)],cwd='/tmp',capture_output=True,text=True,timeout=10)
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == 'FaultMate AI'

def test_no_secret_files_bundled():
    assert not list(ROOT.rglob('.env'))
    assert not list(ROOT.rglob('*.joblib'))
    assert not list(ROOT.rglob('raw_data.csv'))
