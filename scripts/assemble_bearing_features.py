"""Assemble independently verified per-recording bearing CSVs for offline ML.

No raw measurements are invented, no missing features are imputed, and no model
is trained or promoted. Run only after inspecting the original MAT and reviewing
sensor-unit and label provenance. Output defaults should remain under data/converted
(which is Git-ignored). This tool never uploads anything to the network.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from faultmate.integration.ml import FEATURES, EXPECTED_LABELS, parse_feature_csv

FIELDS = (
    'asset_id', 'trial_id', 'source_id', *FEATURES,
    'label', 'label_provenance', 'license',
)
PADERBORN_LICENSE = 'CC BY-NC 4.0'
MIN_ASSETS_PER_CLASS = 5
MAX_ASSEMBLED_BYTES = 10_000_000  # identical to train_ml parse_feature_csv limit


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assemble(input_dir: Path, output: Path, *, require_ready: bool = False) -> dict:
    """Aggregate CSV files, block mixed/ambiguous metadata, and write once safely.

    Files are expected to contain only validated single-recording rows. Values
    may be verified for basic physical consistency, but their actual units and
    label provenance require *prior external human verification*. The generated
    audit records source file hashes for that review, not proof of calibration.
    """
    input_dir = input_dir.resolve()
    output = output.resolve()
    if not input_dir.is_dir():
        raise ValueError('input_directory_missing')
    files = sorted(p for p in input_dir.glob('*.csv') if p.is_file() and p.resolve() != output)
    if not files:
        raise ValueError('no_individual_csv_files')
    if output.exists():
        raise ValueError('output_already_exists')

    rows: list[dict] = []
    inputs: list[dict] = []
    total_bytes = 0
    seen_trials: set[tuple[str, str]] = set()
    seen_recording_values: set[tuple] = set()
    bearing_labels: dict[str, str] = {}
    sources: set[str] = set()
    licenses: set[str] = set()
    label_provenance: defaultdict[str, set[str]] = defaultdict(set)

    for path in files:
        if path.is_symlink():
            raise ValueError('symlinked_input_not_allowed')
        raw = path.read_bytes()
        total_bytes += len(raw)
        if total_bytes > MAX_ASSEMBLED_BYTES:
            raise ValueError('combined_csv_size_exceeds_training_limit')
        batch = parse_feature_csv(raw, training=True)
        if len(batch) != 1:
            raise ValueError(f'expected_one_recording_per_file:{path.name}')
        record = batch[0]
        if record['license'] != PADERBORN_LICENSE:
            raise ValueError(f'incorrect_paderborn_license:{path.name}')
        if record['vibration_peak_m_s2'] + 1e-10 < record['vibration_rms_m_s2']:
            raise ValueError(f'vibration_peak_smaller_than_rms:{path.name}')
        pair = (record['asset_id'], record['trial_id'])
        if pair in seen_trials:
            raise ValueError('duplicate_bearing_and_trial')
        seen_trials.add(pair)
        label = bearing_labels.setdefault(record['asset_id'], record['label'])
        if label != record['label']:
            raise ValueError('bearing_has_conflicting_labels')
        signature = (record['asset_id'], *(record[key] for key in FEATURES))
        if signature in seen_recording_values:
            raise ValueError('duplicate_recording_features_for_asset')
        seen_recording_values.add(signature)
        sources.add(record['source_id'])
        licenses.add(record['license'])
        label_provenance[record['label']].add(record['label_provenance'])
        rows.append(record)
        inputs.append({'filename': path.name, 'sha256': _sha256(raw),
                       'asset_id': record['asset_id'], 'trial_id': record['trial_id']})

    if len(sources) != 1 or len(licenses) != 1:
        raise ValueError('mixed_data_source_or_license')
    counts = Counter(bearing_labels.values())
    ready = all(counts.get(label, 0) >= MIN_ASSETS_PER_CLASS for label in EXPECTED_LABELS)
    if require_ready and not ready:
        raise ValueError('need_at_least_5_independent_bearings_per_class')
    if ready and len({r['label_provenance'] for r in rows}) < 2:
        raise ValueError('label_provenance_not_specific_enough')
    # Model splitting is deliberately deferred to the existing group-aware
    # trainer; no trial is independently assigned to a partition here.
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    output_data = output.read_bytes()
    try:
        # The same parser used by the trainer must accept our final artifact.
        parsed = parse_feature_csv(output_data, training=True)
        if len(parsed) != len(rows):
            raise ValueError('assembly_row_count_mismatch')
    except (ValueError, OSError):
        output.unlink(missing_ok=True)
        raise
    return {
        'status': 'assembled_ready_for_offline_training' if ready else 'assembled_incomplete',
        'training_ready_by_asset_count_only': ready,
        'units_and_labels_rely_on_prior_source_review': True,
        'model_trained': False,
        'model_activated': False,
        'output': str(output),
        'output_sha256': _sha256(output_data),
        'recording_count': len(rows),
        'asset_count': len(bearing_labels),
        'bearing_counts': {label: counts.get(label, 0) for label in EXPECTED_LABELS},
        'source_id': next(iter(sources)),
        'license': next(iter(licenses)),
        'inputs': inputs,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, required=True,
                        help='Directory holding reviewed, individual recording CSVs')
    parser.add_argument('--output', type=Path, required=True,
                        help='Training CSV path (typically under data/converted/)')
    parser.add_argument('--require-ready', action='store_true',
                        help='Fail unless both classes have >=5 independent bearings')
    args = parser.parse_args(argv)
    try:
        report = assemble(args.input_dir, args.output, require_ready=args.require_ready)
    except (ValueError, OSError, csv.Error) as exc:
        print(f'ASSEMBLY_NOT_PUBLISHED: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
