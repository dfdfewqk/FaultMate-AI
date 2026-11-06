"""Synthetic-byte tests only: no actual HUST recording or sensor unit inferred."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts.inventory_hust_original_local_files import (
    HUSTInventoryError, local_hust_inventory, main
)


def test_inventory_real_local_bytes_but_never_source_or_health_proof(tmp_path):
    root = tmp_path / "hust"
    (root / "vibration" / "healthy").mkdir(parents=True)
    sample = root / "vibration" / "healthy" / "N401.mat"
    sample.write_bytes(b"THIS IS FAKE BYTES, NOT HUST ORIGINAL")
    (root / "testbench.png").write_bytes(b"FAKE IMAGE")
    result = local_hust_inventory(root)
    assert result["mat_files_checked"] == 1
    assert result["files_checked"] == 1
    assert result["local_file_list"][0]["relative_path"] == "vibration/healthy/N401.mat"
    assert result["local_file_list"][0]["sha256_actual_local_bytes"] == hashlib.sha256(sample.read_bytes()).hexdigest()
    assert result["publisher_authentication_of_bytes_completed"] is False
    assert result["physical_bearing_count_or_identity_verified"] is False
    assert result["healthy_damage_labels_verified"] is False
    assert result["numerical_signal_si_units_verified"] is False
    assert result["independent_healthy_validation_performed"] is False
    assert result["production_ml_activation_allowed"] is False


def test_archive_count_does_not_become_mat_or_new_bearing_count(tmp_path):
    (tmp_path / "HUST v3.zip").write_bytes(b"FAKE ZIP")
    result = local_hust_inventory(tmp_path)
    assert result["files_checked"] == 1
    assert result["archive_files_checked"] == 1
    assert result["mat_files_checked"] == 0
    assert not result["physical_bearing_count_or_identity_verified"]


def test_duplicate_content_is_flagged_not_accepted_as_distinct_bearings(tmp_path):
    for name in ("A.mat", "B.mat"):
        (tmp_path / name).write_bytes(b"SAME SYNTHETIC BYTES")
    result = local_hust_inventory(tmp_path)
    assert len(result["duplicate_content_sha256"]) == 1
    assert result["duplicate_content_sha256"][0]["first_path"] == "A.mat"
    assert result["duplicate_content_sha256"][0]["duplicate_path"] == "B.mat"


def test_symlink_bearing_file_is_blocked(tmp_path):
    a = tmp_path / "a.mat"
    a.write_bytes(b"FAKE")
    l = tmp_path / "linked.mat"
    l.symlink_to(a)
    with pytest.raises(HUSTInventoryError, match="symlink"):
        local_hust_inventory(tmp_path)


def test_missing_or_symlinked_root_is_blocked(tmp_path):
    with pytest.raises(HUSTInventoryError, match="missing_or_symlink"):
        local_hust_inventory(tmp_path / "not-real")
    root = tmp_path / "root"
    root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(HUSTInventoryError, match="missing_or_symlink"):
        local_hust_inventory(alias)


def test_user_existing_report_cannot_be_overwritten(tmp_path):
    (tmp_path / "data.mat").write_bytes(b"SYNTHETIC")
    target = tmp_path / "important_existing.json"
    target.write_text("PRESERVE_ORIGINAL", encoding="utf-8")
    assert main(["--original-root", str(tmp_path), "--out", str(target)]) == 2
    assert target.read_text(encoding="utf-8") == "PRESERVE_ORIGINAL"


def test_empty_original_folder_does_not_write_fake_report(tmp_path):
    dest = tmp_path / "report.json"
    assert main(["--original-root", str(tmp_path), "--out", str(dest)]) == 2
    assert not dest.exists()


def test_local_inventory_output_is_parseable_and_marked_unapproved(tmp_path):
    (tmp_path / "one.mat").write_bytes(b"SYNTHETIC")
    dest = tmp_path / "report.json"
    assert main(["--original-root", str(tmp_path), "--out", str(dest)]) == 0
    report = json.loads(dest.read_text(encoding="utf-8"))
    assert report["mat_files_checked"] == 1
    assert report["publisher_authentication_of_bytes_completed"] is False
    assert report["production_ml_activation_allowed"] is False
