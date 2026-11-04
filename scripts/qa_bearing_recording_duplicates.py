"""Read-only duplicate check for two recordings from an official Paderborn RAR.

Archive checksum and 80-file inventory must match the curated source catalog.
Physical units are never inferred, converted or approved. No CSV/model output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_paderborn_assets import CATALOG, archive_inventory, validate_catalog
from scripts.convert_mat_to_csv import VIBRATION, CURRENT, choose, read_channels, as_signal


class SourceQualityError(ValueError):
    pass


def md5_stream(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def extract_two_recordings(archive: Path, bearing: str, condition: str, trials: tuple[int, int], sevenzip: str) -> dict:
    assets = {x['id']: x for x in validate_catalog(json.loads(CATALOG.read_text(encoding='utf-8')))}
    asset = assets.get(bearing)
    if asset is None:
        raise SourceQualityError('bearing_not_in_curated_catalog')
    if archive.name.lower() != f'{bearing.lower()}.rar' or archive.is_symlink() or not archive.is_file():
        raise SourceQualityError('archive_name_or_type_invalid')
    if archive.stat().st_size < 100_000_000 or md5_stream(archive) != asset['md5']:
        raise SourceQualityError('archive_size_or_official_md5_mismatch')
    checked = subprocess.run([sevenzip, 't', str(archive)], capture_output=True, timeout=240)
    if checked.returncode != 0:
        raise SourceQualityError(f'archive_integrity_failed:{checked.returncode}')
    listed = subprocess.run([sevenzip, 'l', '-slt', '-ba', str(archive)], capture_output=True, timeout=60)
    if listed.returncode != 0:
        raise SourceQualityError(f'archive_listing_failed:{listed.returncode}')
    listing = listed.stdout.decode('utf-8', errors='replace')
    conditions = archive_inventory(listing, bearing)
    if condition not in conditions:
        raise SourceQualityError('unknown_operating_condition')
    paths = [line[7:].strip() for line in listing.splitlines() if line.startswith('Path = ')]
    needed = []
    for n in trials:
        if n < 1 or n > 20:
            raise SourceQualityError('trial_out_of_range')
        fname = f'{condition}_{bearing}_{n}.mat'
        found = [p for p in paths if p.replace('\\', '/').split('/')[-1].lower() == fname.lower()]
        if len(found) != 1:
            raise SourceQualityError('recording_not_unique_in_archive')
        needed.append((fname, found[0]))
    summaries = []
    signals = []
    with tempfile.TemporaryDirectory(prefix='faultmate-duplicate-qa-') as directory:
        for index, (fname, member) in enumerate(needed):
            dest = Path(directory) / str(index)
            dest.mkdir()
            res = subprocess.run([sevenzip, 'e', '-y', f'-o{dest}', str(archive), member], capture_output=True, timeout=90)
            if res.returncode != 0:
                raise SourceQualityError(f'extract_failed:{res.returncode}')
            p = dest / fname
            if not p.is_file():
                raise SourceQualityError('extracted_recording_missing')
            channels = read_channels(p)
            vib, cur = choose(channels, VIBRATION), choose(channels, CURRENT)
            arrays = [as_signal(vib), as_signal(cur)]
            signals.append(arrays)
            summaries.append({
                'recording': fname,
                'file_sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                'vibration_channel': vib['name'], 'vibration_unit_as_recorded': vib['unit'] or 'unknown',
                'current_channel': cur['name'], 'current_unit_as_recorded': cur['unit'] or 'unknown',
                'vibration_n_samples': arrays[0].size, 'current_n_samples': arrays[1].size,
            })
    same = identical_raw_signals(signals[0], signals[1])
    return {'status': 'real_recordings_inspected', 'bearing_id': bearing,
            'source_archive_md5_verified': True, 'full_archive_integrity': 'passed',
            'condition': condition, 'recordings': summaries,
            'duplicate_signal_samples': same, 'independent_trials': not same,
            'physical_units_verified': False, 'csv_generated': False,
            'model_trained': False, 'training_permitted': False}


def identical_raw_signals(a: list[np.ndarray], b: list[np.ndarray]) -> bool:
    if len(a) != 2 or len(b) != 2:
        raise SourceQualityError('expected_two_matched_channels')
    return all(np.array_equal(x, y) for x, y in zip(a, b))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--bearing', required=True)
    parser.add_argument('--condition', default='N09_M07_F10')
    parser.add_argument('--trials', type=int, nargs=2, default=[17, 18])
    parser.add_argument('--sevenzip')
    args = parser.parse_args(argv)
    sevenzip = args.sevenzip or shutil.which('7z') or shutil.which('7zz')
    if not sevenzip and sys.platform == 'win32':
        candidate = Path(r'C:\Program Files\7-Zip\7z.exe')
        if candidate.is_file():
            sevenzip = str(candidate)
    try:
        if not sevenzip:
            raise SourceQualityError('sevenzip_not_found')
        output = extract_two_recordings(args.archive.absolute(), args.bearing.upper(),
                                        args.condition.upper(), tuple(args.trials), sevenzip)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'quality_inspection_failed', 'reason': str(exc),
                          'training_permitted': False}), file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
