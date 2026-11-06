"""Synthetic source-audit fixtures only: test code not real Paderborn SI evidence."""
import hashlib
import json

import pytest

from scripts import audit_paderborn_960_original_mat_unit_metadata as units
from scripts.audit_paderborn_assets import SourceAuditError


def synthetic_one():
    rows = []
    for condition in ("N09_M07_F10", "N15_M01_F10", "N15_M07_F04", "N15_M07_F10"):
        for trial in range(1, 21):
            name = f"{condition}_K001_{trial}.mat"
            rows.append({
                "recording": name,
                "mat_sha256": hashlib.sha256(name.encode()).hexdigest(),
                "raw_signal_fingerprint": hashlib.sha256((name+"_signal").encode()).hexdigest(),
                "sample_count": 256000,
                "vibration_channel": "vibration_1",
                "current_channel": "phase_current_1",
                "raw_vibration_unit": "unknown",
                "raw_current_unit": "unknown",
                "raw_rms_vibration_unscaled": 0.36,
                "raw_peak_abs_vibration_unscaled": 4.88,
                "raw_rms_current_unscaled": 1.65,
            })
    report = {
        "bearing_id": "K001", "label": "healthy",
        "source_md5_verified": True, "source_archive_md5": "abc123fake",
        "raw_units_verified": False, "si_csv_generated": False,
        "ml_trained": False, "model_activated": False,
        "approved_for_training": False, "inspected_recordings": 80,
        "recordings": rows,
    }
    return report, {"label":"healthy","md5":"abc123fake"}


def test_80_original_mat_units_are_observed_not_falsely_si():
    data, expected=synthetic_one()
    result=units.audit_one_original_report(data,"K001",expected)
    assert result["source_mat_records"]==80
    assert result["both_mat_unit_entries_unknown"]==80
    assert result["original_mat_unit_pair_counts"]==[{
        "vibration_mat_unit":"unknown",
        "phase_current_mat_unit":"unknown",
        "original_mat_files":80,
    }]
    assert result["author_data_scale_and_offset_confirmed"] is False


def test_even_reported_si_channel_string_is_not_external_calibration_proof():
    data, expected=synthetic_one()
    data["recordings"][0]["raw_current_unit"]="A"
    data["recordings"][0]["raw_vibration_unit"]="m/s²"
    result=units.audit_one_original_report(data,"K001",expected)
    assert result["both_mat_unit_entries_unknown"]==79
    assert result["author_data_scale_and_offset_confirmed"] is False


@pytest.mark.parametrize("mutation", [
    lambda x: x["recordings"].pop(),
    lambda x: x["recordings"].append(x["recordings"][0]),
    lambda x: x.update({"raw_units_verified": True}),
    lambda x: x.update({"source_md5_verified": False}),
    lambda x: x.update({"si_csv_generated": True}),
    lambda x: x.update({"model_activated": True}),
    lambda x: x["recordings"][0].update({"vibration_channel":"fake_1"}),
    lambda x: x["recordings"][0].update({"raw_current_unit":""}),
    lambda x: x["recordings"][0].update({"sample_count":0}),
    lambda x: x["recordings"][0].update({"raw_rms_vibration_unscaled":float("nan")}),
])
def test_invalid_source_or_production_si_promotion_rejected(mutation):
    d, expected=synthetic_one()
    mutation(d)
    with pytest.raises(SourceAuditError):
        units.audit_one_original_report(d,"K001",expected)


def test_output_file_must_never_be_overwritten(tmp_path):
    existing=tmp_path/"old-result.json"
    existing.write_text("PRESERVE_SI_EVIDENCE",encoding="utf-8")
    assert units.main(["--raw-audits",str(tmp_path),
                       "--original-evaluation",str(tmp_path/"none.json"),
                       "--out",str(existing)])==2
    assert existing.read_text(encoding="utf-8")=="PRESERVE_SI_EVIDENCE"


def test_unpinned_original_study_fails_before_reporting_units(tmp_path):
    baseline=tmp_path/"baseline.json"
    baseline.write_text(json.dumps({"ml_model_approved":False}),encoding="utf-8")
    with pytest.raises(SourceAuditError,match="SHA_mismatch"):
        units.audit_all_original_metadata(tmp_path,baseline)
