"""Optional real HTTP smoke: starts the local application from outside repo cwd."""
from __future__ import annotations
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]

def smoke():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env={**os.environ,'FAULTMATE_NO_BROWSER':'1','FAULTMATE_PORT':str(port)}
    env.pop('DEEPSEEK_API_KEY',None)
    process=subprocess.Popen([sys.executable,str(ROOT/'scripts/start.py')],cwd='/tmp',
                             env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    url=f'http://127.0.0.1:{port}'
    def send(path,body=None,content_type='application/json'):
        data=None if body is None else (body if isinstance(body,bytes) else json.dumps(body).encode())
        req=Request(url+path,data=data,headers={'Content-Type':content_type} if data else {})
        try:
            with urlopen(req,timeout=5) as res:
                return res.status,res.read(),res.headers
        except HTTPError as err:
            return err.code,err.read(),err.headers
    try:
        for _ in range(70):
            if process.poll() is not None: raise AssertionError('server exited early')
            try:
                status,_,_=send('/api/status')
                if status==200:break
            except (OSError,URLError):pass
            time.sleep(.1)
        else:raise AssertionError('server not ready')
        checks=0
        def check(p,expected=200,body=None,ctype='application/json'):
            nonlocal checks
            status,content,headers=send(p,body,ctype)
            assert status==expected,(p,status,content[:200])
            checks+=1
            return content,headers
        index,_=check('/'); assert b'agent-preview' in index
        js,_=check('/assets/app.js');assert b'agentPreviewButton' in js
        css,_=check('/assets/style.css');assert b'integration-extra' in css
        result,_=check('/api/integration/capabilities');caps=json.loads(result)
        assert caps['agent']['connected'] is False and caps['ml']['inference_enabled'] is False
        check('/api/knowledge/cases');check('/api/knowledge/sources');check('/api/diagnostics/options')
        triage={'case_id':'CONV-001','emergency_hazard':'yes'}
        raw,headers=check('/api/diagnostics/evaluate',body=triage)
        assert json.loads(raw)['state']=='safety_hold' and headers['Cache-Control']=='no-store, private'
        raw,_=check('/api/integration/evidence-preview',body={'triage':triage})
        assert json.loads(raw)['state']=='safety_hold'
        raw,_=check('/api/agent/review',body={'triage':triage,'consent':True})
        assert json.loads(raw)['external_transfer_performed'] is False
        csv=b'asset_id,trial_id,source_id,vibration_rms_m_s2,vibration_peak_m_s2,current_rms_a\nx1,t1,paderborn,1,2,3\n'
        raw,_=check('/api/ml/inspect',body=csv,ctype='text/csv')
        assert json.loads(raw)['status']=='unavailable'
        check('/api/ml/inspect',expected=415,body=csv)
        print('REAL_HTTP_PASS',checks,'checks, subprocess launched from /tmp')
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill()

if __name__=='__main__':smoke()
