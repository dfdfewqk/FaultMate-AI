"""Check the curated Paderborn asset MD5 entries against live Zenodo metadata.

Metadata only. No RAR downloads, conversion, model training, or unit approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.request import urlopen

try:
    from scripts.audit_paderborn_assets import CATALOG, validate_catalog, SourceAuditError
except ModuleNotFoundError:
    # python scripts/verify_zenodo_catalog.py from the repository root
    from audit_paderborn_assets import CATALOG, validate_catalog, SourceAuditError

ZENODO_METADATA = 'https://zenodo.org/api/records/15845309'


def verify_metadata(catalog: dict, metadata: dict) -> dict:
    assets = validate_catalog(catalog)
    entries = metadata.get('files') if isinstance(metadata, dict) else None
    if isinstance(entries, dict):
        entries = entries.get('entries')
    if not isinstance(entries, list):
        raise SourceAuditError('invalid_zenodo_file_inventory')
    discovered: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = entry.get('key')
        if not isinstance(key, str) or not key.endswith('.rar'):
            continue
        checksum = entry.get('checksum')
        if not isinstance(checksum, str) or not checksum.startswith('md5:'):
            raise SourceAuditError(f'zenodo_checksum_missing:{key}')
        if key in discovered:
            raise SourceAuditError(f'zenodo_duplicate_archive:{key}')
        discovered[key] = checksum.removeprefix('md5:').lower()
    verified = []
    for item in assets:
        filename = item['id'] + '.rar'
        if discovered.get(filename) != item['md5']:
            raise SourceAuditError(f'zenodo_checksum_mismatch_or_missing:{filename}')
        verified.append(filename)
    return {'status': 'official_zenodo_metadata_matches_catalog',
            'checked_archives': len(verified),
            'source': ZENODO_METADATA,
            'physical_units_verified': False,
            'raw_archives_downloaded': False,
            'training_permitted': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--metadata-json', type=Path, help='Offline JSON metadata fixture instead of requesting Zenodo')
    args = parser.parse_args(argv)
    try:
        catalog = json.loads(args.catalog.read_text(encoding='utf-8'))
        if args.metadata_json:
            metadata = json.loads(args.metadata_json.read_text(encoding='utf-8'))
        else:
            with urlopen(ZENODO_METADATA, timeout=30) as response:
                metadata = json.load(response)
        result = verify_metadata(catalog, metadata)
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'zenodo_metadata_unverified',
                          'reason': str(exc), 'training_permitted': False}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
