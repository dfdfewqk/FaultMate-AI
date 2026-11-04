"""Synthetic *software* tests only; not evidence of real ML accuracy."""
from __future__ import annotations

import csv
from pathlib import Path
import subprocess
import sys

import pytest
from scripts.assemble_bearing_features import assemble, FIELDS


def one_csv(folder: Path, asset: str, trial: str, *, label='healthy', source='paderborn-bearing-datacenter',
            license='CC BY-NC 4.0', peak=2., rms=1., provenance=None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{asset}-{trial}.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(dict(asset_id=asset, trial_id=trial, source_id=source,
                             vibration_rms_m_s2=rms, vibration_peak_m_s2=peak,
                             current_rms_a=0.4, label=label, license=license,
                             label_provenance=provenance or f'fixture_{label}_{asset}'))
    return path


def test_partial_dataset_is_assembled_but_not_marked_ready(tmp_path):
    directory = tmp_path / 'individual'
    one_csv(directory, 'K001', 'N15_1')
    output = tmp_path / 'bearing_training.csv'
    report = assemble(directory, output)
    assert report['status'] == 'assembled_incomplete'
    assert not report['training_ready_by_asset_count_only']
    assert report['recording_count'] == 1
    assert len(report['inputs'][0]['sha256']) == 64
    assert not report['model_trained'] and not report['model_activated']
    with pytest.raises(ValueError, match='output_already_exists'):
        assemble(directory, output)


def test_minimum_independent_bearing_count_and_full_cli(tmp_path):
    folder = tmp_path / 'individual'
    for index in range(5):
        one_csv(folder, f'K{index+1:03}', 'N15_1', label='healthy')
        one_csv(folder, f'KA{index+1:02}', 'N15_1', label='damaged', rms=4.5, peak=7.)
    dest = tmp_path / 'full.csv'
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'scripts'/'assemble_bearing_features.py'),
                             '--input-dir', str(folder), '--output', str(dest), '--require-ready'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'assembled_ready_for_offline_training' in result.stdout
    with dest.open(newline='', encoding='utf-8') as f:
        assert len(list(csv.DictReader(f))) == 10


def test_reject_duplicate_asset_trial_from_different_csv(tmp_path):
    folder = tmp_path / 'individual'
    p = one_csv(folder, 'K001', 'N15_1')
    (folder/'other.csv').write_bytes(p.read_bytes())
    with pytest.raises(ValueError, match='duplicate_bearing_and_trial'):
        assemble(folder, tmp_path/'out.csv')


def test_conflicting_label_for_same_bearing_fails(tmp_path):
    folder = tmp_path / 'individual'
    one_csv(folder, 'K001', 'N15_1')
    one_csv(folder, 'K001', 'N15_2', label='damaged')
    with pytest.raises(ValueError, match='bearing_has_conflicting_labels'):
        assemble(folder, tmp_path/'out.csv')


def test_bad_physical_peak_fails(tmp_path):
    folder = tmp_path / 'individual'
    one_csv(folder, 'K001', 'N15_1', peak=.2, rms=1.1)
    with pytest.raises(ValueError, match='vibration_peak_smaller_than_rms'):
        assemble(folder, tmp_path/'out.csv')


def test_mixed_sources_and_license_rejected(tmp_path):
    folder = tmp_path / 'individual'
    one_csv(folder, 'K001', 'N15_1')
    one_csv(folder, 'K002', 'N15_1', source='other-dataset')
    with pytest.raises(ValueError, match='mixed_data_source_or_license'):
        assemble(folder, tmp_path/'out.csv')
    one_csv(folder, 'K002', 'N15_1', license='commercial')
    with pytest.raises(ValueError, match='incorrect_paderborn_license'):
        assemble(folder, tmp_path/'out.csv')


def test_require_ready_does_not_write_output(tmp_path):
    folder = tmp_path / 'individual'
    one_csv(folder, 'K001', 'N15_1')
    output = tmp_path / 'out.csv'
    with pytest.raises(ValueError, match='need_at_least_5'):
        assemble(folder, output, require_ready=True)
    assert not output.exists()


def test_requires_one_record_per_file(tmp_path):
    folder = tmp_path / 'individual'
    path = one_csv(folder, 'K001', 'N15_1')
    with path.open('a', encoding='utf-8') as f:
        f.write('K002,N15_2,paderborn-bearing-datacenter,1,2,0.4,healthy,fixture K002,CC BY-NC 4.0\n')
    with pytest.raises(ValueError, match='expected_one_recording_per_file'):
        assemble(folder, tmp_path/'out.csv')


def test_duplicate_feature_record_for_same_bearing_rejected(tmp_path):
    folder = tmp_path / 'individual'
    one_csv(folder, 'K001', 'N15_1')
    one_csv(folder, 'K001', 'N15_2')
    with pytest.raises(ValueError, match='duplicate_recording_features_for_asset'):
        assemble(folder, tmp_path/'out.csv')
