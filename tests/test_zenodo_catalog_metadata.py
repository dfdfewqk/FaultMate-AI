"""Offline fixtures verifying third-party metadata comparison is fail-closed."""
import json

import pytest

from scripts.audit_paderborn_assets import CATALOG, SourceAuditError
from scripts.verify_zenodo_catalog import verify_metadata


def fixture():
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    metadata = {'files': [
        {'key': item['id'] + '.rar', 'checksum': 'md5:' + item['md5']}
        for item in catalog['assets']
    ]}
    return catalog, metadata


def test_valid_source_inventory_matches():
    catalog, metadata = fixture()
    report = verify_metadata(catalog, metadata)
    assert report['checked_archives'] == 12
    assert report['status'] == 'official_zenodo_metadata_matches_catalog'
    assert report['training_permitted'] is False
    assert report['physical_units_verified'] is False


def test_wrong_checksum_rejected():
    catalog, metadata = fixture()
    metadata['files'][0]['checksum'] = 'md5:' + '0'*32
    with pytest.raises(SourceAuditError, match='checksum_mismatch'):
        verify_metadata(catalog, metadata)


def test_missing_archive_rejected():
    catalog, metadata = fixture()
    metadata['files'].pop()
    with pytest.raises(SourceAuditError, match='checksum_mismatch_or_missing'):
        verify_metadata(catalog, metadata)


def test_missing_metadata_inventory_rejected():
    catalog, _ = fixture()
    with pytest.raises(SourceAuditError, match='invalid_zenodo_file_inventory'):
        verify_metadata(catalog, {})


def test_duplicate_metadata_entry_rejected():
    catalog, metadata = fixture()
    metadata['files'].append(metadata['files'][0].copy())
    with pytest.raises(SourceAuditError, match='zenodo_duplicate_archive'):
        verify_metadata(catalog, metadata)
