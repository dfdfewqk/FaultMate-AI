"""Training artifacts cannot silently overwrite a previous evaluation."""
from __future__ import annotations

import csv
from pathlib import Path
import pytest

from scripts.train_ml import train


FIELDS = ('asset_id', 'trial_id', 'source_id', 'vibration_rms_m_s2',
          'vibration_peak_m_s2', 'current_rms_a', 'label',
          'label_provenance', 'license')


def synthetic_input(path: Path):
    # Test fixture only; never claim measured values or real-world accuracy.
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for n in range(6):
            for label, prefix, scale in (('healthy', 'H', 1.), ('damaged', 'D', 4.)):
                for trial in range(2):
                    writer.writerow({
                        'asset_id': f'{prefix}{n}', 'trial_id': f'T{trial}',
                        'source_id': 'test_fixture', 'label': label,
                        'label_provenance': f'test_only_{prefix}{n}',
                        'license': 'test-only',
                        'vibration_rms_m_s2': scale + trial * 0.02,
                        'vibration_peak_m_s2': (scale + trial * 0.02) * 1.5,
                        'current_rms_a': scale / 3 + trial * 0.01,
                    })


def test_rerun_preserves_both_existing_evaluation_files(tmp_path):
    source = tmp_path / 'synthetic.csv'
    synthetic_input(source)
    output = tmp_path / 'evaluation'
    train(source, output, test_fixture_only=True)
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(ValueError, match='evaluation_artifacts_already_exist'):
        train(source, output, test_fixture_only=True)
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before


@pytest.mark.parametrize('name', ['bearing_evaluated.json', 'evaluation_report.json'])
def test_single_existing_artifact_blocks_write(tmp_path, name):
    source = tmp_path / 'synthetic.csv'
    synthetic_input(source)
    output = tmp_path / 'evaluation'
    output.mkdir()
    target = output / name
    target.write_text('DO_NOT_TOUCH', encoding='utf-8')
    with pytest.raises(ValueError, match='evaluation_artifacts_already_exist'):
        train(source, output, test_fixture_only=True)
    assert target.read_text(encoding='utf-8') == 'DO_NOT_TOUCH'
    assert len(list(output.iterdir())) == 1


def test_identical_measurement_different_trial_id_blocks_training(tmp_path):
    source = tmp_path / 'synthetic.csv'
    synthetic_input(source)
    with source.open(encoding='utf-8', newline='') as stream:
        records = list(csv.DictReader(stream))
    # Duplicate one real observation under a new trial ID. This must not count twice.
    duplicate = records[0].copy()
    duplicate['trial_id'] = 'T99'
    records.append(duplicate)
    with source.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    target = tmp_path / 'evaluation'
    with pytest.raises(ValueError, match='duplicate_recording_features_for_asset'):
        train(source, target, test_fixture_only=True)
    assert not target.exists()
