"""Synthetic manifests test input validation, NOT real bearing measurements."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts.audit_paderborn_assets import CATALOG, SourceAuditError
from scripts.combine_paderborn_raw_audits import combine_audits


def _catalog_hash():
    return hashlib.sha256(CATALOG.read_bytes()).hexdigest()


def _fake_report(bearing, *, label, md5, signal="a", duplicate=False):
    condition = "N15_M07_F10"
    def recording(trial, suffix, duplicate_of=None):
        return {
            "recording": f"{condition}_{bearing}_{trial}.mat",
            "mat_sha256": hashlib.sha256(f"mat_{bearing}_{trial}".encode()).hexdigest(),
            "raw_signal_fingerprint": hashlib.sha256(f"{signal}_{suffix}".encode()).hexdigest(),
            "sample_count": 256000,
            "vibration_channel": "vibration_1",
            "current_channel": "phase_current_1",
            "raw_vibration_unit": "unknown",
            "raw_current_unit": "unknown",
            "raw_rms_vibration_unscaled": 1.0,
            "raw_peak_abs_vibration_unscaled": 2.0,
            "raw_rms_current_unscaled": 0.5,
            "condition": condition,
            "trial": trial,
            "duplicate_of": duplicate_of,
        }
    first = recording(17, "first")
    second = recording(18, "first" if duplicate else "second",
                       first["recording"] if duplicate else None)
    repetitions = ([{"recording": second["recording"], "duplicate_of": first["recording"]}]
                   if duplicate else [])
    return {
        "status": "source_verified_raw_units_unapproved",
        "bearing_id": bearing,
        "source_md5_verified": True,
        "source_archive_md5": md5,
        "source_archive_size_bytes": 180_000_000,
        "source_catalog_sha256": _catalog_hash(),
        "archive_inventory_verified": "80_mat_files_across_4_conditions",
        "label": label, "license": "CC BY-NC 4.0",
        "inspected_recordings": 2,
        "unique_raw_signals": 1 if duplicate else 2,
        "duplicate_raw_recordings": repetitions,
        "recordings": [first, second],
        "raw_units_verified": False,
        "si_csv_generated": False,
        "ml_trained": False,
        "model_activated": False,
        "approved_for_training": False,
    }


def _setup(tmp_path, code):
    items = {x["id"]: x for x in json.loads(CATALOG.read_text())["assets"]}
    item = items[code]
    report = _fake_report(code, label=item["label"], md5=item["md5"], signal=code)
    folder = tmp_path / "audit_reports"
    folder.mkdir(exist_ok=True)
    path = folder / f"{code}.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return folder, path, report


def test_partial_verified_cohort_still_blocks_training(tmp_path):
    folder, _, _ = _setup(tmp_path, "K001")
    summary = combine_audits(folder)
    assert summary["status"] == "raw_audit_partial"
    assert summary["verified_independent_bearings"] == 1
    assert summary["verified_by_label"] == {"healthy": 1, "damaged": 0}
    assert len(summary["bearings_missing_audit"]) == 11
    assert summary["physical_units_verified"] is False
    assert summary["training_permitted"] is False
    assert not summary["model_trained"]


def test_same_bearing_raw_duplicate_is_counted_not_double_counted(tmp_path):
    folder, path, report = _setup(tmp_path, "KA04")
    report = _fake_report("KA04", label="damaged", md5=report["source_archive_md5"],
                          signal="real-shaped-fixture", duplicate=True)
    path.write_text(json.dumps(report), encoding="utf-8")
    result = combine_audits(folder)
    assert result["inspected_recordings"] == 2
    assert result["unique_raw_signals_in_inspected_recordings"] == 1
    assert len(result["duplicate_raw_recordings"]) == 1
    assert result["verified_by_label"]["damaged"] == 1
    assert not result["training_permitted"]


def test_manifest_archive_hash_cannot_be_spoofed(tmp_path):
    folder, path, report = _setup(tmp_path, "K001")
    report["source_archive_md5"] = "a" * 32
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(SourceAuditError, match="source_provenance_invalid"):
        combine_audits(folder)


def test_manifest_catalog_version_cannot_be_spoofed(tmp_path):
    folder, path, report = _setup(tmp_path, "K001")
    report["source_catalog_sha256"] = "b" * 64
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(SourceAuditError, match="source_provenance_invalid"):
        combine_audits(folder)


def test_reports_may_not_claim_unverified_units_are_calibrated(tmp_path):
    folder, path, report = _setup(tmp_path, "K001")
    report["raw_units_verified"] = True
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(SourceAuditError, match="unexpected_training_or_unit_claim"):
        combine_audits(folder)


def test_identical_samples_across_physical_bearings_are_rejected(tmp_path):
    folder, _, first = _setup(tmp_path, "K001")
    catalog = {x["id"]: x for x in json.loads(CATALOG.read_text())["assets"]}
    second = _fake_report("K002", label="healthy", md5=catalog["K002"]["md5"], signal="K002")
    second["recordings"][0]["raw_signal_fingerprint"] = first["recordings"][0]["raw_signal_fingerprint"]
    (folder / "K002.json").write_text(json.dumps(second), encoding="utf-8")
    with pytest.raises(SourceAuditError, match="identical_raw_signal_across_bearings"):
        combine_audits(folder)


def test_duplicate_report_for_same_bearing_is_rejected(tmp_path):
    folder, path, _ = _setup(tmp_path, "K001")
    (folder / "copy.json").write_bytes(path.read_bytes())
    with pytest.raises(SourceAuditError, match="unexpected_or_duplicate_bearing_audit"):
        combine_audits(folder)


def test_false_duplicate_claim_fails(tmp_path):
    folder, path, report = _setup(tmp_path, "K001")
    report["recordings"][1]["duplicate_of"] = report["recordings"][0]["recording"]
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(SourceAuditError, match="false_duplicate_claim"):
        combine_audits(folder)


def test_empty_or_symlink_report_directory_rejected(tmp_path):
    folder = tmp_path / "empty"
    folder.mkdir()
    with pytest.raises(SourceAuditError, match="no_raw_audit_reports"):
        combine_audits(folder)


def test_bad_record_source_identity_rejected(tmp_path):
    folder, path, report = _setup(tmp_path, "KA04")
    report["recordings"][0]["recording"] = "N15_M07_F10_K001_17.mat"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(SourceAuditError, match="recording_identity_invalid"):
        combine_audits(folder)
