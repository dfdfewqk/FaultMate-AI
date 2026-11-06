"""Test-only synthetic evaluation files, never published as real ML artifacts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from faultmate.integration import ml
from scripts.review_bearing_model import validate_review


def fixture_files(tmp_path):
    model = {
        'status': 'evaluated_pending_review',
        'scope': 'experimental_bearing_feature_windows_only',
        'source_id': 'paderborn-bearing-datacenter',
        'license': 'CC BY-NC 4.0',
        'data_sha256': 'a' * 64,
        'classes': ['damaged', 'healthy'],
        'feature_names': list(ml.FEATURES),
        'mean': [1., 2., 3.], 'std': [1., 1., 1.],
        'coef': [1., 0., 0.], 'intercept': 0.,
        'provenance_check': {
            'source_verified': True, 'cohort_raw_audit_complete': True,
            'human_calibration_review_present': True,
            'source_audit_sha256': 'b'*64, 'review_sha256': 'c'*64,
            'feature_ledger_sha256': 'd'*64,
            'warning': 'SYNTHETIC test fixture; not genuine calibration evidence',
        },
        'heldout_evaluation': {
            'validation_macro_f1': .8, 'validation_dummy_macro_f1': .4,
            'validation_bearing_macro_f1': .8, 'validation_dummy_bearing_macro_f1': .4,
            'heldout_macro_f1': .7, 'heldout_confusion_matrix': [[2, 0], [1, 1]],
            'heldout_bearing_macro_f1': .75,
            'heldout_bearing_confusion_matrix': [[1, 0], [0, 1]],
            'heldout_bearing_damage_missed_count': 0,
            'heldout_bearing_false_damage_alarm_count': 0,
            'train_asset_count': 6, 'validation_asset_count': 2, 'test_asset_count': 2,
        },
    }
    partitions = {f'bearing_{i}': ('train' if i < 6 else 'validation' if i < 8 else 'test') for i in range(10)}
    evaluated = tmp_path / 'bearing_evaluated.json'
    report = tmp_path / 'evaluation_report.json'
    review = tmp_path / 'review.json'
    evaluated.write_text(json.dumps(model), encoding='utf-8')
    report.write_text(json.dumps({**model['heldout_evaluation'],
                                  'source_id': model['source_id'], 'license': model['license'],
                                  'data_sha256': model['data_sha256'],
                                  'partition_by_asset': partitions}), encoding='utf-8')
    checklist = {key: True for key in (
        'unit_calibration_verified', 'label_provenance_verified',
        'independent_assets_verified', 'heldout_errors_reviewed', 'noncommercial_use_only',
    )}
    review.write_text(json.dumps({**checklist,
        'decision': 'approved_for_experimental_use',
        'evaluated_sha256': hashlib.sha256(evaluated.read_bytes()).hexdigest(),
        'data_sha256': model['data_sha256'],
        'source_audit_sha256': 'b'*64,
        'calibration_review_sha256': 'c'*64,
        'feature_ledger_sha256': 'd'*64,
        'reviewed_by': 'TEST_ONLY_REVIEWER',
        'reviewed_utc': datetime.now(timezone.utc).isoformat(),
        'notes': 'Test fixture only; no real sensor units or physical labels verified.'
    }), encoding='utf-8')
    return evaluated, report, review


def test_evaluation_review_dry_run_does_not_publish(tmp_path):
    evaluated, report, review = fixture_files(tmp_path)
    approved = validate_review(evaluated, report, review)
    assert approved['status'] == 'validated' and approved['review_record']['noncommercial_use_only']
    output = tmp_path / 'bearing_validated.json'
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'review_bearing_model.py'
    args = [sys.executable, str(script), '--evaluated', str(evaluated), '--report', str(report),
            '--review', str(review), '--output', str(output)]
    dry = subprocess.run(args, text=True, capture_output=True)
    assert dry.returncode == 0, dry.stderr
    assert not output.exists()
    applied = subprocess.run(args + ['--apply'], text=True, capture_output=True)
    assert applied.returncode == 0, applied.stderr
    assert output.exists()
    assert json.loads(output.read_text())['review_record']['reviewed_by'] == 'TEST_ONLY_REVIEWER'
    again = subprocess.run(args + ['--apply'], text=True, capture_output=True)
    assert again.returncode == 2  # No overwrite


def test_missing_human_approval_rejected(tmp_path):
    evaluated, report, review = fixture_files(tmp_path)
    data = json.loads(review.read_text())
    data['decision'] = 'pending_review'
    review.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='explicit_human_approval_missing'):
        validate_review(evaluated, report, review)


def test_review_is_bound_to_exact_model_sha(tmp_path):
    evaluated, report, review = fixture_files(tmp_path)
    data = json.loads(evaluated.read_text()); data['mean'][0] += .1
    evaluated.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='human_review_hash_mismatch'):
        validate_review(evaluated, report, review)


def test_report_mismatch_rejected(tmp_path):
    evaluated, report, review = fixture_files(tmp_path)
    data = json.loads(report.read_text()); data['heldout_macro_f1'] = 1
    report.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='evaluation_report_mismatch'):
        validate_review(evaluated, report, review)


def test_synthetic_test_only_source_rejected(tmp_path):
    evaluated, report, review = fixture_files(tmp_path)
    data = json.loads(evaluated.read_text()); data['source_id'] = 'synthetic-test-fixture'
    evaluated.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='source_scope_or_license_not_approved'):
        validate_review(evaluated, report, review)


def test_runtime_model_loader_requires_review_record(tmp_path, monkeypatch):
    # Testing only a fake module filepath to redirect module's fixed models path.
    fake_root = tmp_path / 'app-root'
    fake_path = fake_root / 'faultmate' / 'integration' / 'ml.py'
    models = fake_root / 'models'; models.mkdir(parents=True)
    monkeypatch.setattr(ml, '__file__', str(fake_path))
    evaluated, report, review = fixture_files(tmp_path)
    unsafe = json.loads(evaluated.read_text()); unsafe['status'] = 'validated'
    target = models / 'bearing_validated.json'
    target.write_text(json.dumps(unsafe))
    assert ml.load_validated_model() is None
    reviewed = validate_review(evaluated, report, review)
    target.write_text(json.dumps(reviewed))
    assert ml.load_validated_model() is not None
    reviewed['review_record']['unit_calibration_verified'] = False
    target.write_text(json.dumps(reviewed))
    assert ml.load_validated_model() is None


def test_invalid_partitions_or_baseline_rejected(tmp_path):
    evaluated, report, review = fixture_files(tmp_path)
    data = json.loads(report.read_text())
    data['partition_by_asset']['bearing_0'] = 'test'
    report.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='partition_count_mismatch'):
        validate_review(evaluated, report, review)


def test_missing_actual_provenance_gate_prevents_human_approval(tmp_path):
    evaluated, report, review = fixture_files(tmp_path)
    model = json.loads(evaluated.read_text(encoding="utf-8"))
    model["provenance_check"] = {"status": "synthetic_software_test_only"}
    evaluated.write_text(json.dumps(model), encoding="utf-8")
    with pytest.raises(ValueError, match="real_data_provenance_or_calibration_review_missing"):
        validate_review(evaluated, report, review)


def test_heldout_bearing_matrix_conflict_blocks_review(tmp_path):
    evaluated, report, review = fixture_files(tmp_path)
    model = json.loads(evaluated.read_text(encoding="utf-8"))
    model["heldout_evaluation"]["heldout_bearing_confusion_matrix"] = [[2, 0], [0, 1]]
    evaluated.write_text(json.dumps(model), encoding="utf-8")
    data = json.loads(report.read_text(encoding="utf-8"))
    data["heldout_bearing_confusion_matrix"] = [[2, 0], [0, 1]]
    report.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="heldout_bearing_count_mismatch"):
        validate_review(evaluated, report, review)
