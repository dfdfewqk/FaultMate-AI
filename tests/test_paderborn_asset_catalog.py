"""Synthetic catalog and archive inventory contract tests only."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_paderborn_assets import (
    CATALOG, DAMAGED, HEALTHY, SourceAuditError, archive_inventory, audit,
    validate_catalog,
)


def catalog():
    return json.loads(CATALOG.read_text(encoding='utf-8'))


def listing_for(code: str):
    return '\n'.join(
        f'Path = {code}\\{condition}_{code}_{i}.mat'
        for condition in ('N09_M07_F10','N15_M01_F10','N15_M07_F04','N15_M07_F10')
        for i in range(1, 21)
    )


def test_curated_catalog_has_six_distinct_bearings_per_class():
    rows = validate_catalog(catalog())
    assert len(rows) == 12
    assert {r['id'] for r in rows if r['label'] == 'healthy'} == HEALTHY
    assert {r['id'] for r in rows if r['label'] == 'damaged'} == DAMAGED


def test_catalog_rejects_incorrect_bearing_label():
    doc = catalog()
    doc['assets'][0]['label'] = 'damaged'
    with pytest.raises(SourceAuditError, match='catalog_label_not_supported'):
        validate_catalog(doc)


def test_catalog_rejects_duplicate_asset():
    doc = catalog()
    doc['assets'][1]['id'] = doc['assets'][0]['id']
    with pytest.raises(SourceAuditError, match='duplicate_or_missing'):
        validate_catalog(doc)


def test_catalog_rejects_invalid_md5():
    doc = catalog()
    doc['assets'][0]['md5'] = '0' * 31
    with pytest.raises(SourceAuditError, match='catalog_md5_malformed'):
        validate_catalog(doc)


def test_catalog_rejects_units_claim():
    doc = catalog()
    doc['archive_unit_evidence_status'] = 'verified'
    with pytest.raises(SourceAuditError, match='catalog_units_or_license'):
        validate_catalog(doc)


def test_archive_inventory_accepts_80_recordings_across_4_conditions():
    assert len(archive_inventory(listing_for('KI16'), 'KI16')) == 4


def test_archive_inventory_rejects_wrong_bearing_in_rar():
    with pytest.raises(SourceAuditError, match='unexpected_mat_filename'):
        archive_inventory(listing_for('K001'), 'KI16')


def test_archive_inventory_rejects_duplicate_trial():
    content = listing_for('K001').replace('_K001_20.mat', '_K001_19.mat')
    with pytest.raises(SourceAuditError, match='archive_missing_or_duplicate_trials'):
        archive_inventory(content, 'K001')


def test_archive_inventory_rejects_missing_trial():
    lines = listing_for('K001').splitlines()
    with pytest.raises(SourceAuditError, match='archive_recording_count_invalid'):
        archive_inventory('\n'.join(lines[:-1]), 'K001')


def test_missing_archives_never_permit_training(tmp_path: Path):
    report = audit(tmp_path)
    assert len(report['archive_missing_ids']) == 12
    assert not report['training_permitted']
    assert not report['physical_units_verified']
    assert not report['model_trained']


def test_existing_bad_file_cannot_be_counted_as_verified(tmp_path: Path):
    (tmp_path / 'K001.rar').write_bytes(b'FAKE RAR DATA')
    report = audit(tmp_path)
    assert report['archive_verified_count'] == 0
    assert report['archive_rejected'][0]['id'] == 'K001'
    assert not report['training_permitted']


def test_archive_inventory_rejects_nonstandard_conditions():
    content = listing_for('K001').replace('N09_M07_F10', 'N08_M07_F10')
    with pytest.raises(SourceAuditError, match='archive_conditions_not_official'):
        archive_inventory(content, 'K001')
