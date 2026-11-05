"""Stage 4 safety preflight: real Paderborn data must fail closed without SI proof.

All CSV rows in this file are SYNTHETIC. No real data or models are created.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.ml_stage4_preflight import _row_digest, verify_training_readiness
from scripts.train_ml import train
from faultmate.integration.ml import parse_feature_csv

FIELDS = (
    'asset_id','trial_id','source_id','vibration_rms_m_s2',
    'vibration_peak_m_s2','current_rms_a','label','label_provenance','license'
)


def synthetic_csv(path: Path, *, official_claim: bool = True) -> bytes:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for i in range(6):
            for damaged, prefix, factor in ((False,'K',1.),(True,'KA',4.)):
                writer.writerow({
                    'asset_id': f'{prefix}{i+1:03}' if not damaged else f'KA{i+1:02}',
                    'trial_id': f'N15_M07_F10_{prefix}{i+1:03}_1.mat',
                    'source_id': 'paderborn-bearing-datacenter' if official_claim else 'test_fixture',
                    'vibration_rms_m_s2': factor + i*0.02,
                    'vibration_peak_m_s2': 2*(factor + i*0.02),
                    'current_rms_a': factor / 10 + i*.001,
                    'label': 'damaged' if damaged else 'healthy',
                    'label_provenance': f'test fixture only {i} {prefix}',
                    'license': 'CC BY-NC 4.0' if official_claim else 'test-only',
                })
    return path.read_bytes()


def test_real_source_training_requires_external_audit_and_calibration(tmp_path):
    source = tmp_path / "claimed_source.csv"
    synthetic_csv(source)
    output = tmp_path / "evaluated"
    with pytest.raises(ValueError, match="training_blocked_calibration_or_raw_provenance_not_supplied"):
        train(source, output)
    assert not output.exists()


def test_actual_paderborn_source_cannot_use_synthetic_test_bypass(tmp_path):
    source = tmp_path / "claimed_source.csv"
    synthetic_csv(source)
    output = tmp_path / "evaluated"
    with pytest.raises(ValueError, match="real_source_may_not_use_test_fixture_mode"):
        train(source, output, test_fixture_only=True)
    assert not output.exists()


def test_cli_does_not_expose_synthetic_test_bypass(tmp_path):
    source = tmp_path / "test.csv"
    synthetic_csv(source, official_claim=False)
    output = tmp_path / "evaluated"
    cli = Path(__file__).resolve().parents[1] / 'scripts' / 'train_ml.py'
    result = subprocess.run([sys.executable,str(cli),str(source),'--output',str(output)],
                            capture_output=True,text=True)
    assert result.returncode == 2
    assert "training_blocked_calibration_or_raw_provenance_not_supplied" in result.stderr
    assert not output.exists()


def test_unsupplied_review_blocks_even_if_raw_summary_reports_all_sources(tmp_path):
    from zipfile import ZipFile
    # A stand-in for a trusted full 960 recording report is not sufficient
    # to establish numerical sensor SI calibration.
    raw = synthetic_csv(tmp_path / "source.csv")
    rows = parse_feature_csv(raw, training=True)
    summary = tmp_path / 'summary.json'
    summary.write_text(json.dumps({
        'cohort_raw_audit_complete': True, 'verified_independent_bearings': 12,
        'inspected_recordings': 960, 'fully_audited_by_label': {'healthy':6,'damaged':6},
        'physical_units_verified': False,
    }))
    reports_dir = tmp_path / 'source_audits'
    reports_dir.mkdir()
    with pytest.raises(ValueError, match='training_blocked_calibration_or_raw_provenance_not_supplied'):
        verify_training_readiness(
            raw, rows, raw_audits_dir=reports_dir, raw_audit_summary=summary,
            source_review=None, evidence_document=None, feature_ledger=None)


def test_feature_row_digest_changes_on_tamper(tmp_path):
    raw = synthetic_csv(tmp_path / "source.csv", official_claim=False)
    row = parse_feature_csv(raw, training=True)[0]
    original = _row_digest(row)
    assert len(original) == 64
    row['vibration_rms_m_s2'] += .01
    assert original != _row_digest(row)
