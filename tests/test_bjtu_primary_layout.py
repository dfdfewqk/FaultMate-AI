"""Primary-author BJTU CSV layout, physical asset identity, no-raw-data claims.

No original dataset or paid AI request in these unit tests.
"""
from __future__ import annotations

import copy
import json
import subprocess

import pytest

from scripts import audit_bjtu_primary_layout as primary
from scripts.audit_external_healthy_compatibility import assess_inventory


def _published():
    return json.loads(primary.PUBLISHED_LAYOUT.read_text(encoding="utf-8"))


def _fake_36_normal_paths():
    paths = []
    for number, (speed, load) in enumerate(sorted(primary.CONDITIONS), start=1):
        for obj in sorted(primary.SENSOR_OBJECTS):
            paths.append(
                "BJTU_RAO_Bogie_Datasets/M0_G0_LA0_RA0/"
                f"Sample_{number}/data_{obj}_M0_G0_LA0_RA0_"
                f"{speed}Hz_{load}kN.csv"
            )
    return paths


def test_original_author_51_states_nine_sessions_four_csv_and_one_normal():
    d = _published()
    primary.verify_published_layout(d)
    s = d["reported_folder_structure"]
    assert s["normal_label"] == "M0_G0_LA0_RA0"
    assert s["normal_health_state_folders"] == 1
    assert s["labeled_health_state_folders"] == 51
    assert s["faulty_health_state_folders"] == 50
    assert s["samples_per_health_state"] == 9
    assert s["csv_files_per_sample"] == 4
    assert s["expected_total_csv_files_if_original_complete"] == 51 * 9 * 4
    assert s["expected_normal_csv_files_if_original_complete"] == 9 * 4
    assert d["evidence_gaps"]["number_independent_healthy_physical_bearings_verified"] is None


def test_publisher_public_attribution_is_not_automatic_commercial_dataset_rights():
    d = _published()
    assert "data source is indicated" in d["source_licensing_evidence"]["guide_usage_statement"]
    assert d["source_licensing_evidence"]["source_guide_attribution_required"] is True
    assert d["source_licensing_evidence"]["commercial_permission_explicitly_confirmed"] is False
    assert d["source_licensing_evidence"]["machine_readable_dataset_license_confirmed"] is False
    assert d["evidence_gaps"]["license_for_commercial_integration_verified"] is False


@pytest.mark.parametrize("path,value", [
    ("reported_folder_structure", ("normal_health_state_folders", 9)),
    ("reported_folder_structure", ("csv_files_per_sample", 24)),
    ("reported_folder_structure", ("labeled_health_state_folders", 52)),
    ("reported_folder_structure", ("expected_normal_csv_files_if_original_complete", 324)),
    ("reported_folder_structure", ("all_channels_nominal_sample_rate_hz", 50000)),
    ("source_licensing_evidence", ("commercial_permission_explicitly_confirmed", True)),
    ("evidence_gaps", ("normal_sample_sessions_are_independent_physical_bearings", True)),
    ("evidence_gaps", ("healthy_specificity_measured", True)),
    ("evidence_gaps", ("original_csv_bytes_read", True)),
    ("evidence_gaps", ("number_independent_healthy_physical_bearings_verified", 9)),
    ("source_document_sensor_info", ("same_bearing_or_operating_condition_as_paderborn", True)),
])
def test_cannot_fabricate_original_bearings_verified_csv_or_licensing(path, value):
    doc = copy.deepcopy(_published())
    name, change = value
    doc[path][name] = change
    with pytest.raises(primary.PublishedSourceError):
        primary.verify_published_layout(doc)


def test_relative_filename_index_complete_does_not_become_physical_bearing_validation():
    paths = _fake_36_normal_paths()
    report = primary.inspect_metadata_only_healthy_paths(paths)
    assert report["metadata_paths_checked"] == 36
    assert report["nine_source_conditions_and_four_sensor_groups_layout_complete"] is True
    assert report["distinct_normal_physical_bearing_count"] is None
    assert report["source_csv_file_integrity_verified"] is False
    assert report["healthy_bearing_independent_holdout_proven"] is False
    assert report["new_normal_specificity_measured"] is False
    assert report["frozen_paderborn_model_approved_for_bjtu"] is False


def test_partial_35_filenames_cannot_prove_complete_original_36():
    report = primary.inspect_metadata_only_healthy_paths(_fake_36_normal_paths()[:-1])
    assert report["nine_source_conditions_and_four_sensor_groups_layout_complete"] is False


@pytest.mark.parametrize("wrong", [
    "BJTU_RAO_Bogie_Datasets/../../secrets/M0_G0_LA0_RA0/Sample_1/x.csv",
    "BJTU_RAO_Bogie_Datasets/M0_G0_LA1_RA0/Sample_1/data_motor_M0_G0_LA0_RA0_20Hz_0kN.csv",
    "BJTU_RAO_Bogie_Datasets/M0_G0_LA0_RA0/Sample_10/data_motor_M0_G0_LA0_RA0_20Hz_0kN.csv",
    "BJTU_RAO_Bogie_Datasets/M0_G0_LA0_RA0/Sample_1/data_motor_M0_G0_LA0_RA0_100Hz_0kN.csv",
    "BJTU_RAO_Bogie_Datasets/M0_G0_LA0_RA0/Sample_1/data_motor_M0_G0_LA0_RA0_20Hz_15kN.csv",
])
def test_fake_healthy_labels_paths_conditions_are_blocked(wrong):
    with pytest.raises(primary.PublishedSourceError):
        primary.inspect_metadata_only_healthy_paths([wrong])


def test_duplicate_filename_rejected_as_independent_recording():
    first = _fake_36_normal_paths()[0]
    with pytest.raises(primary.PublishedSourceError, match="repeated"):
        primary.inspect_metadata_only_healthy_paths([first, first])


def test_same_sample_folder_cannot_contain_two_different_operating_conditions():
    paths = _fake_36_normal_paths()
    paths[0] = paths[0].replace("20Hz_-10kN", "40Hz_-10kN")
    with pytest.raises(primary.PublishedSourceError, match="session_condition_conflict"):
        primary.inspect_metadata_only_healthy_paths(paths)


def test_filename_counts_are_not_frozen_paderborn_normal_specificity():
    original = assess_inventory()
    assert original["new_healthy_bearings_validated"] == 0
    assert original["false_positive_rate_measured"] is False
    result = primary.inspect_metadata_only_healthy_paths(_fake_36_normal_paths())
    assert result["frozen_paderborn_model_approved_for_bjtu"] is False


def test_no_network_cli_is_report_only_no_existing_files_affected(tmp_path):
    report = tmp_path / "source_inventory.json"
    assert primary.main(["--out", str(report)]) == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["documented_normal_csv_files"] == 36
    assert data["source_healthy_physical_bearings_verified"] == 0
    assert data["false_positive_rate_measured"] is False
    assert data["drive"]["public_drive_probe_requested"] is False
    assert data["drive"]["original_csv_files_downloaded"] is False
    original = report.read_bytes()
    assert primary.main(["--out", str(report)]) == 2
    assert report.read_bytes() == original


def test_gdown_metadata_only_success_still_cannot_certify_original_files(monkeypatch):
    class FakeCompleted:
        returncode = 0
        stdout = json.dumps([
            {"url": "https://drive.google.com/file/d/test",
             "path": "BJTU_RAO_Bogie_Datasets/M0_G0_LA0_RA0/Sample_1/report.csv"}
        ])
        stderr = ""

    def fake_run(cmd, **kwargs):
        assert "--json" in cmd
        assert "--folder" in cmd
        assert "--no-cookies" in cmd
        assert cmd[1:3] == ["-m", "gdown"]
        return FakeCompleted()

    monkeypatch.setattr(primary.subprocess, "run", fake_run)
    result = primary.probe_public_folder_metadata()
    assert result["public_drive_probe_requested"] is True
    assert result["google_drive_folder_reachable"] is True
    assert result["metadata_entries_returned"] == 1
    assert result["public_entry_path_sample"] == [
        "BJTU_RAO_Bogie_Datasets/M0_G0_LA0_RA0/Sample_1/report.csv"
    ]
    assert result["metadata_listing_complete"] is False
    assert result["normal_folder_structurally_verified"] is False
    assert result["source_csv_sha256_verified"] is False
    assert result["independent_normal_physical_bearings_verified"] == 0


@pytest.mark.parametrize("failure", [1, 2])
def test_drive_metadata_probe_fail_does_not_fabricate_missing_normal_bearings(
        monkeypatch, failure):
    class FakeCompleted:
        returncode = failure
        stdout = ""
        stderr = "Google may require login (not saved in report)"

    monkeypatch.setattr(primary.subprocess, "run",
                        lambda *args, **kwargs: FakeCompleted())
    result = primary.probe_public_folder_metadata()
    assert result["google_drive_folder_reachable"] is None
    assert result["public_drive_error_class"] == "metadata_listing_failed_or_limited"
    assert result["source_csv_sha256_verified"] is False


def test_drive_metadata_probe_timeout_not_treated_as_no_data(monkeypatch):
    def fail(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="gdown", timeout=30)

    monkeypatch.setattr(primary.subprocess, "run", fail)
    result = primary.probe_public_folder_metadata(timeout_seconds=30)
    assert result["google_drive_folder_reachable"] is None
    assert result["public_drive_error_class"] == "metadata_probe_unavailable_or_timed_out"
