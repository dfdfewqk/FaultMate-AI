"""Synthetic-only tests for Paderborn raw-signal audit contracts.

Fixtures are NOT claimed to be real sensor data or model evaluations.
"""
from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat

from scripts.audit_paderborn_assets import SourceAuditError
from scripts.audit_paderborn_raw_recordings import (
    describe_mat, raw_signal_fingerprint, audit_one_archive,
)


def make_mat(path: Path, *, offset: float = 0, unit_vib: str = "", unit_cur: str = ""):
    signals = np.empty((1, 2), dtype=object)
    signals[0, 0] = {
        "Name": "vibration_1",
        "Data": np.linspace(-1, 1, 48) + offset,
        "Unit": unit_vib,
    }
    signals[0, 1] = {
        "Name": "phase_current_1",
        "Data": np.linspace(-.5, .5, 48),
        "Unit": unit_cur,
    }
    savemat(path, {"Y": signals})


def test_same_numeric_recording_different_storage_is_duplicate():
    vib = np.linspace(-1, 1, 256)
    cur = np.cos(np.linspace(0, 2, 256))
    assert raw_signal_fingerprint(vib, cur) == raw_signal_fingerprint(vib.copy(), cur.copy())


def test_changed_current_channel_is_not_duplicate():
    vib = np.linspace(-1, 1, 256)
    cur = np.ones(256)
    altered = cur.copy()
    altered[1] += .01
    assert raw_signal_fingerprint(vib, cur) != raw_signal_fingerprint(vib, altered)


def test_changed_vibration_channel_is_not_duplicate():
    vib = np.linspace(-1, 1, 256)
    other = vib.copy()
    other[-1] += .25
    cur = np.ones(256)
    assert raw_signal_fingerprint(vib, cur) != raw_signal_fingerprint(other, cur)


def test_negative_zero_does_not_change_numeric_signature():
    vib = np.ones(256)
    a = np.zeros(256)
    b = np.zeros(256)
    b[0] = -0.0
    assert raw_signal_fingerprint(vib, a) == raw_signal_fingerprint(vib, b)


def test_fingerprint_rejects_channel_size_mismatch():
    with pytest.raises(SourceAuditError, match="paired_signal_shape_mismatch"):
        raw_signal_fingerprint(np.arange(256.), np.arange(255.))


def test_fingerprint_rejects_nan():
    signal = np.ones(256)
    signal[0] = np.nan
    with pytest.raises(SourceAuditError, match="invalid_raw_signal"):
        raw_signal_fingerprint(signal, np.ones(256))


def test_mat_struct_unit_missing_not_misrepresented_as_si(tmp_path):
    source = tmp_path / "N15_M07_F10_K001_1.mat"
    make_mat(source)
    report = describe_mat(source, source.name)
    assert report["sample_count"] == 48
    assert report["raw_vibration_unit"] == "unknown"
    assert report["raw_current_unit"] == "unknown"
    assert "raw_rms_vibration_unscaled" in report
    assert "vibration_rms_m_s2" not in report
    assert report["mat_sha256"]


def test_mat_channel_names_and_recorded_units_not_invented(tmp_path):
    source = tmp_path / "N15_M07_F10_K001_1.mat"
    make_mat(source, unit_vib="m/s²", unit_cur="A")
    report = describe_mat(source, source.name)
    assert report["raw_vibration_unit"] == "m/s²"
    assert report["raw_current_unit"] == "A"
    assert "vibration_rms_m_s2" not in report


def test_unverified_archive_cannot_be_audited(tmp_path):
    fake = tmp_path / "K001.rar"
    fake.write_bytes(b"NOT A REAL ARCHIVE")
    with pytest.raises(SourceAuditError, match="official_source_md5_mismatch"):
        audit_one_archive(fake, "K001", sevenzip="7z")


def test_wrong_name_cannot_impersonate_known_archive(tmp_path):
    fake = tmp_path / "random.rar"
    fake.write_bytes(b"NOT A REAL ARCHIVE")
    with pytest.raises(SourceAuditError, match="wrong_or_missing_source_archive"):
        audit_one_archive(fake, "K001", sevenzip="7z")
