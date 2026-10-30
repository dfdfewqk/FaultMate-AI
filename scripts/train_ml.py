"""Offline experimental bearing feature training. Run only on properly licensed, labeled real data.

This script never promotes models to deployment. Do not train on P2 illustrative cases.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from faultmate.integration.ml import FEATURES, EXPECTED_LABELS, parse_feature_csv


def train(input_csv: Path, output_dir: Path):
    import numpy as np
    from sklearn.model_selection import train_test_split
    from sklearn.linear_model import LogisticRegression
    from sklearn.dummy import DummyClassifier
    from sklearn.metrics import classification_report, confusion_matrix, f1_score
    from sklearn.preprocessing import StandardScaler

    raw=input_csv.read_bytes()
    rows=parse_feature_csv(raw,training=True)
    if len({r['source_id'] for r in rows}) != 1 or len({r['license'] for r in rows}) != 1:
        raise ValueError('mixed_source_or_license_requires_separate_training')
    if len({r['label_provenance'] for r in rows}) < 2:
        raise ValueError('label_provenance_not_specific_enough')
    per_asset={}
    for r in rows:
        group=per_asset.setdefault(r['asset_id'],set())
        group.add(r['label'])
    if any(len(labels)!=1 for labels in per_asset.values()):
        raise ValueError('asset_crosses_labels')
    groups_by_label=Counter(next(iter(v)) for v in per_asset.values())
    if any(groups_by_label.get(label,0)<5 for label in EXPECTED_LABELS):
        raise ValueError('need_at_least_5_independent_assets_per_class')
    asset_names=sorted(per_asset)
    asset_labels=[next(iter(per_asset[a])) for a in asset_names]
    # Group-stratified splitting: no bearing asset may appear in two partitions.
    trval, test=train_test_split(asset_names,test_size=.20,random_state=42,stratify=asset_labels)
    tr, val=train_test_split(trval,test_size=.25,random_state=43,
            stratify=[next(iter(per_asset[a])) for a in trval])
    partition={g:'train' for g in tr}
    partition.update({g:'validation' for g in val})
    partition.update({g:'test' for g in test})
    def sample(groups):
        filtered=[r for r in rows if r['asset_id'] in groups]
        return np.asarray([[r[f] for f in FEATURES] for r in filtered],dtype=float), np.asarray([r['label'] for r in filtered])
    xtr,ytr=sample(set(tr)); xv,yv=sample(set(val)); xt,yt=sample(set(test))
    if not all(len(set(y))==2 for y in (ytr,yv,yt)):
        raise ValueError('class_missing_in_partition')
    scaler=StandardScaler().fit(xtr)
    trn=scaler.transform(xtr); valn=scaler.transform(xv); testn=scaler.transform(xt)
    candidate=LogisticRegression(max_iter=1000,random_state=42).fit(trn,ytr)
    baseline=DummyClassifier(strategy='most_frequent').fit(trn,ytr)
    candidate_f1=f1_score(yv,candidate.predict(valn),average='macro',zero_division=0)
    baseline_f1=f1_score(yv,baseline.predict(valn),average='macro',zero_division=0)
    if candidate_f1 <= baseline_f1:
        raise ValueError('candidate_does_not_beat_validation_baseline')
    ypred=candidate.predict(testn)
    metrics={'validation_macro_f1':round(float(candidate_f1),4),
             'validation_dummy_macro_f1':round(float(baseline_f1),4),
             'heldout_macro_f1':round(float(f1_score(yt,ypred,average='macro',zero_division=0)),4),
             'heldout_confusion_matrix':confusion_matrix(yt,ypred,labels=list(EXPECTED_LABELS)).tolist(),
             'heldout_classification':classification_report(yt,ypred,labels=list(EXPECTED_LABELS),output_dict=True,zero_division=0),
             'train_asset_count':len(tr),'validation_asset_count':len(val),'test_asset_count':len(test)}
    assert not (set(tr)&set(val) or set(tr)&set(test) or set(val)&set(test))
    model={'status':'evaluated_pending_review','scope':'experimental_bearing_feature_windows_only',
           'classes':list(candidate.classes_),'feature_names':list(FEATURES),
           'coef':candidate.coef_[0].astype(float).tolist(),
           'intercept':float(candidate.intercept_[0]),
           'mean':scaler.mean_.astype(float).tolist(),
           'std':scaler.scale_.astype(float).tolist(),
           'data_sha256':hashlib.sha256(raw).hexdigest(),
           'source_id':rows[0]['source_id'],'license':rows[0]['license'],
           'algorithm':'logistic_regression_scaled','split_level':'asset_id',
           'generated_utc':datetime.now(timezone.utc).isoformat(),
           'heldout_evaluation':metrics}
    output_dir.mkdir(parents=True,exist_ok=True)
    (output_dir/'bearing_evaluated.json').write_text(json.dumps(model,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output_dir/'evaluation_report.json').write_text(json.dumps({**metrics,
        'data_sha256':model['data_sha256'], 'source_id':model['source_id'],
        'license':model['license'],'partition_by_asset':partition,
        'note':'교육용 실험 데이터 평가. 현장 안전·고장 예측 성능 보증 아님.'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return metrics


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('input_csv',type=Path)
    ap.add_argument('--output',type=Path,default=Path('models/evaluation'))
    args=ap.parse_args()
    try: print(json.dumps(train(args.input_csv,args.output),ensure_ascii=False,indent=2))
    except (ValueError,OSError) as exc: print('TRAINING_NOT_PUBLISHED:',str(exc),file=sys.stderr);sys.exit(2)
