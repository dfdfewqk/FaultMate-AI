"""New-source intake checks use SYNTHETIC bytes, not real bearing data.

None of the tests makes a field approval claim, reads network or changes a model.
"""
import copy
import hashlib
import json

import pytest

from scripts.verify_new_bearing_original_files import (
    SCHEMA, SOURCES, IntakeError, inspect_source, main
)


def _manifest(source="hust_bearing_v3"):
    return {
        "schema": SCHEMA,
        "status": "candidate_not_author_verified",
        "source_id": source,
        "primary_dataset_url": SOURCES[source]["primary_dataset_url"],
        "license": SOURCES[source]["license"],
        "source_numeric_si_calibration_verified": False,
        "physical_label_provenance_author_verified": False,
        "automatically_activate_runtime_model": False,
        "proposed_specimens": [],
    }


def _add(root, manifest, *, physical="HUST-A", filename="vibration.mat",
         label="healthy", data=b"SYNTHETIC FAKE SIGNAL RAW BYTES"):
    (root / filename).write_bytes(data)
    manifest["proposed_specimens"].append({
        "claimed_physical_specimen_id": physical,
        "claimed_original_label": label,
        "files": [{"relative_path": filename,
                   "sha256": hashlib.sha256(data).hexdigest()}],
    })
    return manifest


def test_real_bytes_can_be_checked_but_not_called_real_independent_labels(tmp_path):
    m = _add(tmp_path, _manifest())
    result = inspect_source(tmp_path, m)
    assert result["verified_original_file_count"] == 1
    assert result["verified_source_bytes"] is True
    assert result["original_source_file_evidence"][0]["files"][0]["original_bytes_verified"]
    assert result["source_protocol"]["vibration_hz"] == 51200
    assert result["source_protocol"]["motor_current_hz"] is None
    assert result["source_protocol"]["paired_vibration_and_motor_current"] is False
    assert result["compatibility_with_existing_paderborn_12_feature_model"].startswith("INCOMPATIBLE")
    assert result["physical_identity_and_health_labels_independently_verified"] is False
    assert result["signal_channels_and_numeric_si_units_verified"] is False
    assert result["normal_false_alarm_rate_and_specificity_measured"] is False
    assert result["production_ml_activation_allowed"] is False
    assert result["separate_new_domain_model_training_approved"] is False
    assert result["model_changed_or_trained"] is False


def test_empty_real_source_is_not_claimed_as_verified(tmp_path):
    result = inspect_source(tmp_path, _manifest())
    assert result["status"] == "NO_NEW_ORIGINAL_BYTES_SUPPLIED"
    assert result["verified_source_bytes"] is False
    assert result["claimed_physical_specimen_count"] == 0


@pytest.mark.parametrize("field,value", [
    ("source_id", "other_dataset"),
    ("primary_dataset_url", "https://malicious.example/other"),
    ("license", "CC0"),
    ("source_numeric_si_calibration_verified", True),
    ("physical_label_provenance_author_verified", True),
    ("automatically_activate_runtime_model", True),
    ("status", "author_verified"),
    ("schema", "obsolete"),
])
def test_not_allowed_to_fake_publisher_or_units(tmp_path, field, value):
    m = _add(tmp_path, _manifest())
    m[field] = value
    with pytest.raises(IntakeError):
        inspect_source(tmp_path, m)


def test_changed_original_bytes_are_rejected(tmp_path):
    m = _add(tmp_path, _manifest())
    (tmp_path / "vibration.mat").write_bytes(b"ALTERED_FAKE_TEST_BYTES")
    with pytest.raises(IntakeError, match="original_source_file_sha256_mismatch"):
        inspect_source(tmp_path, m)


@pytest.mark.parametrize("relative", [
    "../outside.mat", "/etc/file.mat", "data/../../secret.mat",
    "a\\b.mat", ".git/config", "not-a-mat.exe", "",
])
def test_path_escape_and_non_data_types_are_refused(tmp_path, relative):
    m = _add(tmp_path, _manifest())
    m["proposed_specimens"][0]["files"][0]["relative_path"] = relative
    with pytest.raises(IntakeError):
        inspect_source(tmp_path, m)


def test_symlink_is_rejected_even_if_it_stays_inside_source_root(tmp_path):
    m = _add(tmp_path, _manifest())
    (tmp_path / "inside.mat").symlink_to(tmp_path / "vibration.mat")
    m["proposed_specimens"][0]["files"][0]["relative_path"] = "inside.mat"
    with pytest.raises(IntakeError, match="symlink"):
        inspect_source(tmp_path, m)


def test_duplicate_original_file_bytes_cannot_be_two_specimens(tmp_path):
    m = _add(tmp_path, _manifest())
    _add(tmp_path, m, physical="HUST-B", filename="other.mat",
         label="damaged", data=b"SYNTHETIC FAKE SIGNAL RAW BYTES")
    with pytest.raises(IntakeError, match="duplicate_source_file_or_raw_sha256"):
        inspect_source(tmp_path, m)


def test_existing_paderborn_bearings_cannot_be_rebranded_new(tmp_path):
    m = _add(tmp_path, _manifest("paderborn_2016"),
             physical="K006", data=b"OLD_K006_FAKE_BEARING")
    with pytest.raises(IntakeError, match="physical_specimen_id_reused_or_invalid"):
        inspect_source(tmp_path, m)


def test_paderborn_modality_alone_does_not_approve_or_validate(tmp_path):
    m = _add(tmp_path, _manifest("paderborn_2016"),
             physical="NEW-EXPERIMENTAL-NOT-REAL", data=b"FAKE")
    result = inspect_source(tmp_path, m)
    assert result["source_protocol"]["paired_vibration_and_motor_current"] is True
    assert result["compatibility_with_existing_paderborn_12_feature_model"].startswith("INPUT_PROTOCOL_ONLY")
    assert result["physical_identity_and_health_labels_independently_verified"] is False
    assert result["frozen_paderborn_model_scoring_allowed"] is False
    assert result["production_ml_activation_allowed"] is False


def test_output_never_overwrites_existing_report(tmp_path):
    m = _add(tmp_path, _manifest())
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(m), encoding="utf-8")
    destination = tmp_path / "keep.json"
    destination.write_text("PRESERVE_PREVIOUS_RESULTS", encoding="utf-8")
    assert main(["--manifest", str(manifest), "--original-root", str(tmp_path),
                 "--out", str(destination)]) == 2
    assert destination.read_text(encoding="utf-8") == "PRESERVE_PREVIOUS_RESULTS"


def test_metadata_only_cli_reports_no_new_raw_bytes(tmp_path, capsys):
    manifest = tmp_path / "candidate.json"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    rc = main(["--manifest", str(manifest), "--original-root", str(tmp_path)])
    assert rc == 0
    output = json.loads(capsys.readouterr().out)
    assert output["verified_original_file_count"] == 0
    assert output["new_independent_validation"] is False
    assert output["production_ml_activation"] is False
