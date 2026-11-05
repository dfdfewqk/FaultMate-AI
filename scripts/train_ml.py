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


def train(input_csv: Path, output_dir: Path, *, raw_audits_dir: Path | None = None,
          raw_audit_summary: Path | None = None, source_review: Path | None = None,
          evidence_document: Path | None = None, feature_ledger: Path | None = None,
          test_fixture_only: bool = False):
    # Evaluations are review evidence; a rerun must never silently replace them.
    if (output_dir / "bearing_evaluated.json").exists() or (output_dir / "evaluation_report.json").exists():
        raise ValueError("evaluation_artifacts_already_exist; choose_a_fresh_output_directory")
    import numpy as np
    from sklearn.model_selection import train_test_split
    from sklearn.linear_model import LogisticRegression
    from sklearn.dummy import DummyClassifier
    from sklearn.metrics import classification_report, confusion_matrix, f1_score
    from sklearn.preprocessing import StandardScaler

    raw=input_csv.read_bytes()
    rows=parse_feature_csv(raw,training=True)
    if test_fixture_only:
        # NEVER expose this bypass on the CLI or permit an actual Paderborn
        # dataset to masquerade as a synthetic software test.
        if any(r['source_id'] == 'paderborn-bearing-datacenter' or
               r['license'] == 'CC BY-NC 4.0' for r in rows):
            raise ValueError('real_source_may_not_use_test_fixture_mode')
        provenance = {'status': 'synthetic_software_test_only'}
    else:
        from scripts.ml_stage4_preflight import verify_training_readiness
        provenance = verify_training_readiness(
            raw, rows, raw_audits_dir=raw_audits_dir,
            raw_audit_summary=raw_audit_summary, source_review=source_review,
            evidence_document=evidence_document, feature_ledger=feature_ledger)
    # Different trial IDs can still represent the same physical recording.
    # Detect identical feature vectors within a bearing before fitting/splitting.
    seen_by_asset = set()
    for record in rows:
        signature = (record['asset_id'], *(record[name] for name in FEATURES))
        if signature in seen_by_asset:
            raise ValueError('duplicate_recording_features_for_asset')
        seen_by_asset.add(signature)
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
    # Repeated trials from one bearing are NOT independent test units.
    # Majority classification by mean P(healthy) yields ONE vote per bearing.
    # Holdout results report both window-level and bearing-level metrics.
    def per_bearing_predictions(model, groups, x_scaled):
        ordered_rows = [r for r in rows if r['asset_id'] in groups]
        probabilities = model.predict_proba(x_scaled)
        healthy_index = list(model.classes_).index('healthy')
        grouped = {}
        for record, probs in zip(ordered_rows, probabilities):
            grouped.setdefault(record['asset_id'], []).append(float(probs[healthy_index]))
        names = sorted(grouped)
        truth = [next(iter(per_asset[name])) for name in names]
        predictions = ['healthy' if float(np.mean(grouped[name])) >= 0.5 else 'damaged'
                       for name in names]
        return names, truth, predictions

    _, vy_asset, vp_asset = per_bearing_predictions(candidate, set(val), valn)
    _, vy_base, vp_base = per_bearing_predictions(baseline, set(val), valn)
    validation_asset_f1 = f1_score(vy_asset, vp_asset, average='macro', zero_division=0)
    validation_asset_baseline = f1_score(vy_base, vp_base, average='macro', zero_division=0)
    candidate_f1=f1_score(yv,candidate.predict(valn),average='macro',zero_division=0)
    baseline_f1=f1_score(yv,baseline.predict(valn),average='macro',zero_division=0)
    if validation_asset_f1 <= validation_asset_baseline:
        raise ValueError('candidate_does_not_beat_bearing_level_validation_baseline')
    if candidate_f1 <= baseline_f1:
        raise ValueError('candidate_does_not_beat_validation_baseline')
    ypred=candidate.predict(testn)
    heldout_names, heldout_bearing_truth, heldout_bearing_pred = per_bearing_predictions(
        candidate, set(test), testn)
    bearing_matrix = confusion_matrix(
        heldout_bearing_truth, heldout_bearing_pred, labels=list(EXPECTED_LABELS)).tolist()
    matrix=confusion_matrix(yt,ypred,labels=list(EXPECTED_LABELS)).tolist()
    # Classes are damaged, healthy. Surface the safety-relevant two error types
    # explicitly rather than leaving them buried in a confusion matrix.
    split_counts = {
        name: dict(Counter(next(iter(per_asset[asset])) for asset in group))
        for name, group in (('train', tr), ('validation', val), ('test', test))
    }
    metrics={'validation_macro_f1':round(float(candidate_f1),4),
             'validation_dummy_macro_f1':round(float(baseline_f1),4),
             'validation_bearing_macro_f1':round(float(validation_asset_f1),4),
             'validation_dummy_bearing_macro_f1':round(float(validation_asset_baseline),4),
             'heldout_macro_f1':round(float(f1_score(yt,ypred,average='macro',zero_division=0)),4),
             'heldout_confusion_matrix':matrix,
             'heldout_damage_missed_count':int(matrix[0][1]),
             'heldout_false_damage_alarm_count':int(matrix[1][0]),
             'heldout_bearing_macro_f1':round(float(f1_score(
                 heldout_bearing_truth, heldout_bearing_pred,
                 average='macro', zero_division=0)),4),
             'heldout_bearing_confusion_matrix':bearing_matrix,
             'heldout_bearing_damage_missed_count':int(bearing_matrix[0][1]),
             'heldout_bearing_false_damage_alarm_count':int(bearing_matrix[1][0]),
             'heldout_bearing_predictions':[
                 {'asset_id': name, 'actual_label': actual, 'predicted_experimental_label': predicted}
                 for name, actual, predicted in zip(heldout_names, heldout_bearing_truth, heldout_bearing_pred)],
             'evaluation_limitation':'Held-out assets are few; repeated trials do not increase independent bearing count.',
             'heldout_classification':classification_report(yt,ypred,labels=list(EXPECTED_LABELS),output_dict=True,zero_division=0),
             'split_asset_counts_by_label':split_counts,
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
           'provenance_check':provenance,
           'heldout_evaluation':metrics}
    output_dir.mkdir(parents=True,exist_ok=True)
    with (output_dir/'bearing_evaluated.json').open('x', encoding='utf-8') as fp:
        fp.write(json.dumps(model,ensure_ascii=True,indent=2)+'\n')
    with (output_dir/'evaluation_report.json').open('x', encoding='utf-8') as fp:
        fp.write(json.dumps({**metrics,
            'data_sha256':model['data_sha256'], 'source_id':model['source_id'],
            'license':model['license'],'partition_by_asset':partition,
            'note':'교육용 실험 데이터 평가. 현장 안전·고장 예측 성능 보증 아님.'},ensure_ascii=True,indent=2)+'\n')
    return metrics


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('input_csv',type=Path)
    ap.add_argument('--output',type=Path,default=Path('models/evaluation'))
    ap.add_argument('--raw-audits-dir',type=Path,help='12 source-verified per-bearing raw audit JSONs')
    ap.add_argument('--raw-audit-summary',type=Path,help='Recomputed 960-recording aggregate report')
    ap.add_argument('--source-review',type=Path,help='Human-reviewed dataset-specific stored SI units')
    ap.add_argument('--evidence-document',type=Path,help='Hashed primary calibration document/author reply')
    ap.add_argument('--feature-ledger',type=Path,help='Each feature row bound to original MAT SHA256')
    args=ap.parse_args()
    try: print(json.dumps(train(
        args.input_csv, args.output, raw_audits_dir=args.raw_audits_dir,
        raw_audit_summary=args.raw_audit_summary, source_review=args.source_review,
        evidence_document=args.evidence_document, feature_ledger=args.feature_ledger),
        ensure_ascii=False, indent=2))
    except (ValueError,OSError) as exc: print('TRAINING_NOT_PUBLISHED:',str(exc),file=sys.stderr);sys.exit(2)
