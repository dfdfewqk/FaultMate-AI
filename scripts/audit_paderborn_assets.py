"""Fail-closed source-archive readiness audit for a documented Paderborn subset.

This NEVER asserts SI units, extracts training features, or trains/activates a model.
Uses official per-file Zenodo MD5 hashes and the KAt paper's bearing labels.
No downloads; safe to run on a directory containing existing RAR files.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

CATALOG = Path(__file__).resolve().parents[1] / 'docs' / 'PADERBORN_TRAINING_ASSETS.json'
CONDITION = re.compile(r'^(N\d{2}_M\d{2}_F\d{2})_([A-Z]{1,2}\d{2,3})_(\d+)\.mat$', re.I)
OFFICIAL_CONDITIONS = {'N09_M07_F10', 'N15_M01_F10', 'N15_M07_F04', 'N15_M07_F10'}
HEALTHY = {f'K{i:03d}' for i in range(1, 7)}
# Curated subset of accelerated-lifetime damaged bearings from
# Lessmeier et al. 2016, Table 5. Artificially damaged examples are excluded.
DAMAGED = {'KA04', 'KA16', 'KB23', 'KI04', 'KI16', 'KI18'}


class SourceAuditError(ValueError):
    pass


def validate_catalog(document: dict) -> list[dict]:
    if not isinstance(document, dict) or document.get('version') != 1:
        raise SourceAuditError('catalog_version_invalid')
    if (document.get('archive_unit_evidence_status') != 'unverified'
        or document.get('license') != 'CC BY-NC 4.0'):
        raise SourceAuditError('catalog_units_or_license_misrepresented')
    assets = document.get('assets')
    if not isinstance(assets, list) or len(assets) != 12:
        raise SourceAuditError('catalog_requires_12_independent_bearing_assets')
    seen = set()
    for item in assets:
        if not isinstance(item, dict):
            raise SourceAuditError('invalid_catalog_row')
        asset = item.get('id')
        if not isinstance(asset, str) or asset in seen:
            raise SourceAuditError('duplicate_or_missing_asset_id')
        seen.add(asset)
        expected_label = 'healthy' if asset in HEALTHY else 'damaged' if asset in DAMAGED else None
        expected_origin = 'none' if expected_label == 'healthy' else 'accelerated_lifetime'
        if (expected_label is None or item.get('label') != expected_label
            or item.get('damage_origin') != expected_origin):
            raise SourceAuditError(f'catalog_label_not_supported_by_primary_paper:{asset}')
        md5 = item.get('md5')
        if not isinstance(md5, str) or not re.fullmatch(r'[0-9a-f]{32}', md5):
            raise SourceAuditError(f'catalog_md5_malformed:{asset}')
    if seen != HEALTHY | DAMAGED:
        raise SourceAuditError('catalog_asset_inventory_invalid')
    return sorted(assets, key=lambda a: a['id'])


def archive_inventory(listing: str, bearing_id: str) -> dict[str, int]:
    conditions = {}
    total = 0
    for line in listing.splitlines():
        if not line.startswith('Path = '):
            continue
        filename = line[7:].strip().replace('\\', '/').rsplit('/', 1)[-1]
        if not filename.lower().endswith('.mat'):
            continue
        match = CONDITION.fullmatch(filename)
        if match is None or match.group(2).upper() != bearing_id:
            raise SourceAuditError(f'unexpected_mat_filename:{filename}')
        cond, _, run = match.groups()
        cond = cond.upper()
        conditions.setdefault(cond, []).append(int(run))
        total += 1
    if len(conditions) != 4 or total != 80:
        raise SourceAuditError(f'archive_recording_count_invalid:{bearing_id}')
    if set(conditions) != OFFICIAL_CONDITIONS:
        raise SourceAuditError(f'archive_conditions_not_official:{bearing_id}')
    for cond, runs in conditions.items():
        if sorted(runs) != list(range(1, 21)):
            raise SourceAuditError(f'archive_missing_or_duplicate_trials:{bearing_id}:{cond}')
    return {cond: 20 for cond in sorted(conditions)}


def archive_md5(path: Path) -> str:
    h = hashlib.md5(usedforsecurity=False)
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def audit(root: Path, catalog: Path = CATALOG, *, sevenzip: str | None = None) -> dict:
    entries = validate_catalog(json.loads(catalog.read_text(encoding='utf-8')))
    if not root.is_dir():
        raise SourceAuditError('archive_directory_not_found')
    verified = []
    missing = []
    rejected = []
    executable = sevenzip or shutil.which('7z') or shutil.which('7zz')
    if executable is None and sys.platform == 'win32':
        default = Path(r'C:\Program Files\7-Zip\7z.exe')
        if default.is_file():
            executable = str(default)
    for row in entries:
        ident = row['id']
        path = root / f'{ident}.rar'
        if not path.exists():
            missing.append(ident)
            continue
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size < 100_000_000:
                raise SourceAuditError('invalid_archive_file_or_size')
            if archive_md5(path) != row['md5']:
                raise SourceAuditError('archive_md5_mismatch')
            if executable is None:
                raise SourceAuditError('sevenzip_missing')
            test = subprocess.run([executable, 't', str(path)], capture_output=True,
                                  check=False, timeout=240)
            if test.returncode != 0:
                raise SourceAuditError(f'archive_integrity_failed:{test.returncode}')
            listing = subprocess.run([executable, 'l', '-slt', '-ba', str(path)], capture_output=True,
                                     check=False, timeout=60)
            if listing.returncode != 0:
                raise SourceAuditError(f'archive_listing_failed:{listing.returncode}')
            conditions = archive_inventory(listing.stdout.decode('utf-8', errors='replace'), ident)
            verified.append({'id': ident, 'label': row['label'], 'conditions': conditions})
        except (OSError, SourceAuditError, subprocess.SubprocessError) as exc:
            rejected.append({'id': ident, 'reason': str(exc)})
    labels = Counter(item['label'] for item in verified)
    ready_by_asset_count = all(labels[label] >= 5 for label in ('healthy', 'damaged'))
    return {
        'status': 'source_archives_verified_but_units_unverified' if len(verified) == len(entries)
                  else 'archive_readiness_incomplete',
        'archive_verified_count': len(verified),
        'archive_missing_ids': missing,
        'archive_rejected': rejected,
        'archive_verified': verified,
        'verified_independent_asset_counts': dict(labels),
        'minimum_class_assets_met': ready_by_asset_count,
        'physical_units_verified': False,
        'csv_generated': False,
        'model_trained': False,
        'model_activated': False,
        'training_permitted': False,
        'blocking_reason': 'Paderborn MAT Unit metadata are blank; source-specific unit scaling evidence is not yet verified',
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--sevenzip', help='Path to 7z.exe')
    args = parser.parse_args(argv)
    try:
        result = audit(args.root, args.catalog, sevenzip=args.sevenzip)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'catalog_audit_failed', 'reason': str(exc), 'training_permitted': False}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if not result['archive_rejected'] and not result['archive_missing_ids'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
