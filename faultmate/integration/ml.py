"""Fail-closed, JSON-only ML inference for validated bearing feature models.

No pickle loading, no arbitrary file read paths, no invented predictions.
"""
from __future__ import annotations
import csv
import io
import json
import math
import os
from pathlib import Path

FEATURES = ('vibration_rms_m_s2','vibration_peak_m_s2','current_rms_a')
EXPECTED_LABELS = ('damaged','healthy')
MAX_CSV_BYTES = 256_000


def _parse_float(value: str) -> float:
    x = float(value)
    if not math.isfinite(x) or x < 0 or x > 1e7:
        raise ValueError('non_finite_or_out_of_range_feature')
    return x


def parse_feature_csv(data: bytes, training: bool = False) -> list[dict]:
    if len(data) > (10_000_000 if training else MAX_CSV_BYTES) or len(data) == 0:
        raise ValueError('csv_size_invalid')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError as exc:
        raise ValueError('csv_must_be_utf8') from exc
    reader = csv.DictReader(io.StringIO(text))
    required = {'asset_id','trial_id','source_id',*FEATURES}
    if training:
        required |= {'label','label_provenance','license'}
    try:
        header = reader.fieldnames
    except csv.Error as exc:
        raise ValueError('malformed_csv_header') from exc
    if not header or not required.issubset(header):
        raise ValueError('missing_required_columns')
    if len(header) != len(set(header)) or len(header) > 24:
        raise ValueError('invalid_csv_header')
    output = []
    observed = set()
    parsed_rows = iter(reader)
    while True:
        try:
            row = next(parsed_rows)
        except StopIteration:
            break
        except csv.Error as exc:
            # Python's CSV reader raises csv.Error for oversized fields and
            # malformed quoting. Reject user data instead of returning HTTP 500.
            raise ValueError('malformed_csv_row') from exc
        if len(output) >= (100_000 if training else 2000):
            raise ValueError('too_many_csv_rows')
        if None in row or any(row[x] is None for x in required):
            raise ValueError('malformed_csv_row')
        for name in ('asset_id','trial_id','source_id'):
            if not 1 <= len(row[name].strip()) <= 80:
                raise ValueError('invalid_identifier')
        pair = (row['asset_id'],row['trial_id'])
        if pair in observed:
            raise ValueError('duplicate_asset_trial')
        observed.add(pair)
        record = {k:row[k].strip() for k in ('asset_id','trial_id','source_id')}
        record.update({key:_parse_float(row[key]) for key in FEATURES})
        if training:
            if row['label'] not in EXPECTED_LABELS or not row['label_provenance'].strip() or not row['license'].strip():
                raise ValueError('unverified_label_metadata')
            record.update({k:row[k].strip() for k in ('label','label_provenance','license')})
        output.append(record)
    if not output:
        raise ValueError('no_rows')
    return output


def load_validated_model() -> dict | None:
    model_path = Path(__file__).resolve().parents[2] / 'models' / 'bearing_validated.json'
    if not model_path.is_file():
        return None
    try:
        model = json.loads(model_path.read_text(encoding='utf-8'))
        if not isinstance(model, dict):
            return None
        if (model.get('status') != 'validated' or model.get('feature_names') != list(FEATURES)
            or model.get('classes') != list(EXPECTED_LABELS)
            or not model.get('data_sha256') or not model.get('heldout_evaluation')
            or not isinstance(model.get('source_id'),str) or not model['source_id']):
            return None
        for key in ('mean','std','coef'):
            if len(model.get(key,[])) != len(FEATURES) or not all(isinstance(x,(float,int)) and math.isfinite(x) for x in model[key]):
                return None
        if (any(x<=0 for x in model['std']) or not isinstance(model.get('intercept'),(float,int))
            or not math.isfinite(model['intercept'])):
            return None
        return model
    except (OSError,ValueError,TypeError,KeyError):
        return None


def capabilities() -> dict:
    ready = load_validated_model() is not None
    return {'connected':ready,'trained':ready,'inference_enabled':ready,
            'requires_independent_validated_fault_labels':True,
            'model_scope':'experimental_bearing_feature_windows_only' if ready else None,
            'status':'validated' if ready else 'unavailable'}


def inspect_csv(data: bytes) -> dict:
    try:
        rows = parse_feature_csv(data)
    except (ValueError,TypeError) as exc:
        return {'status':'unsupported_input','inference_performed':False,'confirmed_fault':False,'safe_to_work':False,
                'message':str(exc)}
    model = load_validated_model()
    if model is None:
        return {'status':'unavailable','inference_performed':False,'confirmed_fault':False,'safe_to_work':False,
                'checked_rows':len(rows),
                'message':'CSV 형식은 확인했으나 검증된 베어링 ML 모델이 없으므로 예측하지 않습니다.'}
    try:
        if any(row['source_id'] != model['source_id'] for row in rows):
            raise ValueError('source_not_supported_by_model')
        values = []
        for row in rows:
            z = sum(model['coef'][i] * ((row[name]-model['mean'][i])/model['std'][i]) for i,name in enumerate(FEATURES)) + model['intercept']
            # Output a model score, NOT a real-world failure probability.
            score = 1/(1+math.exp(-max(-50,min(50,z))))
            # scikit binary classifier coef corresponds to classes_[1] = healthy.
            values.append({'asset_id':row['asset_id'],'trial_id':row['trial_id'],
                           'predicted_experimental_label':'healthy' if score >= 0.5 else 'damaged',
                           'model_score':round(score,4)})
        return {'status':'validated','inference_performed':True,'confirmed_fault':False,'safe_to_work':False,
                'model_scope':'experimental_bearing_feature_windows_only','rows':values,
                'warning':'실험 베어링 데이터 기준 비교 지표입니다. 현장 설비 고장 확률이나 정비 허가가 아닙니다.'}
    except (ValueError,TypeError) as exc:
        return {'status':'unsupported_input','inference_performed':False,'confirmed_fault':False,'safe_to_work':False,
                'message':str(exc)}
