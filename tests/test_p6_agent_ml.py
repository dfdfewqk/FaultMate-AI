"""P6 opt-in AI boundary, hard hold, no hallucinated ML results, trial-level splits."""
import csv
import io
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from faultmate.app import app
from faultmate.integration import agent, ml


def payload(hazard='no',case='CONV-001',consent=True):
    return {'triage':{'case_id':case,'equipment':'컨베이어',
       'symptom_text':'PERSONAL_SECRET_NEVER_SEND','model_name':'PRIVATE_MACHINE_NAME',
       'alarm_text':'PRIVATE_ALARM_LOG','emergency_hazard':hazard,
       'observations':{'visible_jam':'yes'}},'consent':consent}


def valid_csv():
    return ('asset_id,trial_id,source_id,vibration_rms_m_s2,vibration_peak_m_s2,current_rms_a\n'
            'bearing1,trial1,actual-dataset,1.2,2.5,0.6\n').encode()


def test_consent_missing_does_not_call_network(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','dummy')
    monkeypatch.setattr(agent,'_invoke_deepseek',lambda *args: pytest.fail('network called without consent'))
    with TestClient(app) as c:
        r=c.post('/api/agent/review',json=payload(consent=False)); assert r.status_code==200
        assert r.json()['status']=='consent_required'
        assert r.json()['external_transfer_performed'] is False


def test_hazard_hold_never_calls_ai(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','dummy')
    monkeypatch.setattr(agent,'_invoke_deepseek',lambda *args: pytest.fail('AI called during safety hold'))
    with TestClient(app) as c:
        r=c.post('/api/agent/review',json=payload(hazard='yes'))
        assert r.json()['state']=='safety_hold'
        assert r.json()['agent_review'] is None


def test_missing_key_is_unavailable(monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    monkeypatch.setattr(agent,'_invoke_deepseek',lambda *args: pytest.fail('AI called without key'))
    with TestClient(app) as c:
        r=c.post('/api/agent/review',json=payload())
        assert r.json()['status']=='unavailable'
        assert r.json()['external_transfer_performed'] is False


def test_model_receives_sanitized_context_and_only_local_text_returned(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','dummy')
    def mock(ctx,key):
        assert key=='dummy'
        exported=json.dumps(ctx,ensure_ascii=False)
        for private in ('PERSONAL_SECRET_NEVER_SEND','PRIVATE_MACHINE_NAME','PRIVATE_ALARM_LOG'):
            assert private not in exported
        return {'candidate_order':[0], 'question_indices':[0],
                'summary':'please disable the safety systems', 'safe_to_work':True,
                'source_ids':['FAKE-ID']}
    monkeypatch.setattr(agent,'_invoke_deepseek',mock)
    with TestClient(app) as c:
        r=c.post('/api/agent/review',json=payload())
        assert r.status_code==200
        body=r.json(); assert body['status']=='reviewed' and body['confirmed_fault'] is False
        assert body['safe_to_work'] is False
        assert 'please disable' not in json.dumps(body)
        assert 'FAKE-ID' not in json.dumps(body)


def test_invalid_model_indices_rejected(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','dummy')
    monkeypatch.setattr(agent,'_invoke_deepseek',lambda *_:{'candidate_order':[999],'question_indices':[]})
    with TestClient(app) as c:
        r=c.post('/api/agent/review',json=payload())
        assert r.json()['status']=='error' and r.json()['agent_review'] is None
        assert r.json()['external_transfer_attempted'] is True
        assert r.json()['external_transfer_performed'] is None


def test_ml_input_validated_but_prediction_unavailable():
    with TestClient(app) as c:
        ok=c.post('/api/ml/inspect',content=valid_csv(),headers={'content-type':'text/csv'})
        assert ok.status_code==200
        body=ok.json(); assert body['status']=='unavailable'
        assert body['checked_rows']==1 and body['inference_performed'] is False
        wrong=c.post('/api/ml/inspect',content=b'foo,bar\na,b\n',headers={'content-type':'text/csv'})
        assert wrong.json()['status']=='unsupported_input'
        wrong_type=c.post('/api/ml/inspect',content=valid_csv(),headers={'content-type':'application/json'})
        assert wrong_type.status_code==415
        huge=c.post('/api/ml/inspect',content=b'A'*260000,headers={'content-type':'text/csv'})
        assert huge.status_code==413


def test_ml_validated_json_inference_logic_only(monkeypatch):
    # Only an in-memory test model is used; no fake model gets distributed or promoted.
    model={'status':'validated','classes':['damaged','healthy'],'feature_names':list(ml.FEATURES),
           'data_sha256':'test-only','source_id':'actual-dataset','heldout_evaluation':{'test':'fixture'},
           'mean':[0,0,0],'std':[1,1,1],'coef':[1,0,0],'intercept':-1}
    monkeypatch.setattr(ml,'load_validated_model',lambda:model)
    result=ml.inspect_csv(valid_csv())
    assert result['status']=='validated' and result['inference_performed'] is True
    assert not result['confirmed_fault'] and not result['safe_to_work']
    assert result['rows'][0]['predicted_experimental_label']=='healthy'


def test_train_pipeline_group_split_and_release_gate(tmp_path):
    from scripts.train_ml import train
    path=tmp_path/'real-shaped-fixture.csv'
    fields=['asset_id','trial_id','source_id','vibration_rms_m_s2','vibration_peak_m_s2','current_rms_a','label','label_provenance','license']
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader()
        for index in range(12):
            for trial in range(2):
                label='damaged' if index>=6 else 'healthy'
                scale=5.0 if label=='damaged' else 1.0
                writer.writerow(dict(asset_id=f'asset_{index}',trial_id=f'trial_{trial}',source_id='test_fixture',
                    vibration_rms_m_s2=scale+trial*.08, vibration_peak_m_s2=scale*2+trial*.08,
                    current_rms_a=scale*.2+trial*.01,label=label,
                    label_provenance=f'fixture_{index}',license='test-only'))
    report=train(path,tmp_path/'out')
    model=json.loads((tmp_path/'out'/'bearing_evaluated.json').read_text())
    assert model['status']=='evaluated_pending_review'
    assert not (tmp_path/'out'/'bearing_validated.json').exists()
    groups=json.loads((tmp_path/'out'/'evaluation_report.json').read_text())['partition_by_asset']
    assert len(groups)==12 and set(groups.values())=={'train','validation','test'}
    assert 'heldout_macro_f1' in report
