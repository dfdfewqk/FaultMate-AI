"""Synthetic source report fixtures; never claim fake SHA to be real HUST data."""
from copy import deepcopy
import hashlib

import pytest

from scripts import reconcile_hust_original_physical_identity as study


def fixture():
    rows = []
    for fault in ("N", "I", "O", "B", "IB", "IO", "OB"):
        for bearing_type in range(4, 9):
            if bearing_type == 4 and fault in ("B", "IB"):
                continue
            for load in (0, 2, 4):
                name = f"{fault}{bearing_type}0{load}.mat"
                rows.append({
                    "file": name, "sha256": hashlib.sha256(name.encode()).hexdigest(),
                    "bytes": 6000000,
                    "sample_count": 512000 if len(rows) < 81 else 400000,
                })
    assert len(rows) == 99
    return {
        "schema": "faultmate_hust_hanoi_original_99_verified_research_only_v1",
        "source_id": "cbv7jyx4p9", "published_version": 3,
        "source_index_sha256": study.SOURCE_SHA_INDEX,
        "real_original_mat_files_checked": 99,
        "all_original_bytes_match_first_party_file_sha256": True,
        "all_original_mat_source_numeric_signals_parsed": True,
        "actual_independent_healthy_physical_specimens_verified": 0,
        "actual_independent_damaged_physical_specimens_verified": 0,
        "original_stored_numeric_si_calibration_verified": False,
        "model_activation_allowed": False,
        "original_paper_reported_healthy_physical_prototypes": 3,
        "naming_vs_paper_healthy_specimen_count_requires_author_confirmation": True,
        "observed_normal_file_naming_codes": ["N4","N5","N6","N7","N8"],
        "individual_sha256_results": rows,
    }


def test_33_name_groups_3_loads_each_are_not_physical_specimen_identities():
    p = study.verify_real_original_metadata(fixture())
    assert p["actual_source_sha_verified_original_mat_recordings"] == 99
    assert p["observed_original_filename_codes"] == 33
    assert p["observed_normal_filename_codes"] == 5
    assert p["observed_damaged_filename_codes"] == 28
    assert p["author_paper_reported_healthy_physical_prototypes"] == 3
    assert p["author_paper_reported_damaged_physical_prototypes"] == 27
    assert len(p["name_code_mappings_are_unverified_specimen_proxies"]) == 33
    assert p["source_mat_files_with_non_nominal_sample_lengths"] == 18
    assert p["verified_physical_healthy_specimen_count"] == 0
    assert p["verified_physical_damaged_specimen_count"] == 0
    assert p["new_independent_normal_evaluation_permitted"] is False
    assert p["production_ml_activation_allowed"] is False
    assert p["scientific_status"].startswith("BLOCKED_")


@pytest.mark.parametrize("key,value", [
    ("source_id","unknown"), ("published_version",2),
    ("source_index_sha256","0"*64),
    ("all_original_bytes_match_first_party_file_sha256",False),
    ("actual_independent_healthy_physical_specimens_verified",3),
    ("model_activation_allowed",True),
    ("original_stored_numeric_si_calibration_verified",True),
    ("original_paper_reported_healthy_physical_prototypes",5),
    ("naming_vs_paper_healthy_specimen_count_requires_author_confirmation",False),
])
def test_unverified_original_or_wrongly_promoted_group_rejected(key,value):
    data=fixture()
    data[key]=value
    with pytest.raises(study.PhysicalIdentityAuditError):
        study.verify_real_original_metadata(data)


def test_duplicate_source_bytes_rejected():
    d=fixture()
    d["individual_sha256_results"][1]["sha256"]=d["individual_sha256_results"][0]["sha256"]
    with pytest.raises(study.PhysicalIdentityAuditError, match="duplicate"):
        study.verify_real_original_metadata(d)


def test_one_load_missing_does_not_count_as_distinct_bearing():
    d=fixture()
    d["individual_sha256_results"][0]["file"]="N408.mat"
    with pytest.raises(study.PhysicalIdentityAuditError):
        study.verify_real_original_metadata(d)


def test_fewer_99_originals_must_not_produce_scientific_report():
    d=fixture()
    d["individual_sha256_results"].pop()
    with pytest.raises(study.PhysicalIdentityAuditError, match="99_mat"):
        study.verify_real_original_metadata(d)


def test_no_source_data_does_not_allow_file_output(tmp_path):
    dest=tmp_path/"preserve.json"
    dest.write_text("IMPORTANT_PREVIOUS", encoding="utf-8")
    rc=study.main(["--official-source-report",str(tmp_path/"absent.json"),
                   "--out",str(dest)])
    assert rc == 2
    assert dest.read_text(encoding="utf-8")=="IMPORTANT_PREVIOUS"


def test_modified_real_report_bytes_must_not_run(tmp_path):
    original=tmp_path/"original.json"
    original.write_text("{}",encoding="utf-8")
    dest=tmp_path/"fresh.json"
    rc=study.main(["--official-source-report",str(original), "--out",str(dest)])
    assert rc==2
    assert not dest.exists()
