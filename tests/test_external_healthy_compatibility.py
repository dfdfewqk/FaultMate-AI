"""No-network research source compatibility regression.

Public source METADATA is checked here; this is *not* a newly collected
healthy-bearing dataset and the tests do not calculate a false alarm rate.
"""
from __future__ import annotations

import copy
import json

import pytest

from scripts.audit_external_healthy_compatibility import (
    SOURCE_FILE, SourceReadinessError, assess_inventory,
    assess_source_metadata, _validate_fixed_source_inventory,
)
from faultmate.integration.ml import load_validated_model


def _inventory():
    return json.loads(SOURCE_FILE.read_text(encoding="utf-8"))


def test_research_model_rejects_all_four_source_metadata_candidates():
    status = assess_inventory()
    assert status["no_approved_healthy_source"] is True
    assert status["new_healthy_bearings_validated"] == 0
    assert status["overall_accuracy_measured"] is False
    assert status["false_positive_rate_measured"] is False
    assert status["ml_predictions_performed"] is False
    assert load_validated_model() is None
    result = {r["source_id"]: r for r in status["results"]}
    assert set(result) == {"paderborn_healthy_reuse", "kaist_varying_load",
                           "kaist_varying_speed", "phm24_bjtu_rao_bogie"}
    assert all(not r["direct_frozen_model_prediction_allowed"]
               and not r["healthy_specificity_measured"]
               and not r["new_independent_healthy_qualification"]
               for r in result.values())


def test_six_old_healthy_bearings_cannot_be_renamed_as_new_test():
    result = {r["source_id"]: r for r in assess_inventory()["results"]}
    assert "all_healthy_physical_bearings_already_opened" in (
        result["paderborn_healthy_reuse"]["blocking_reasons"])
    assert "previously_used_bearing_in_new_test" in (
        result["paderborn_healthy_reuse"]["blocking_reasons"])


def test_kaist_new_healthy_status_does_not_justify_applying_frozen_model():
    result = {r["source_id"]: r for r in assess_inventory()["results"]}
    for name in ("kaist_varying_load", "kaist_varying_speed"):
        reasons = result[name]["blocking_reasons"]
        assert "new_independent_healthy_physical_bearings_not_proven" in reasons
        assert "original_measurement_hashes_not_verified" in reasons
        assert "four_paderborn_operating_conditions_not_equivalent" in reasons
        assert "vibration_sampling_rate_differs_from_paderborn_64khz" in reasons
        assert "current_sampling_rate_differs_from_paderborn_64khz" in reasons
        assert "independent_site_domain_shift_not_reviewed" in reasons


@pytest.mark.parametrize("field,value", [
    ("nominal_sample_rate_vibration_hz", 64000),
    ("nominal_sample_rate_current_hz", 64000),
    ("operating_condition_count", 4),
    ("matched_paderborn_condition_protocol", True),
    ("license", "CC BY-NC 4.0"),
    ("source_url", "https://untrusted.invalid"),
    ("independent_data_acquisition_site", False),
    ("independent_physical_asset_inventory_verified", True),
    ("source_archive_integrity_verified", True),
    ("source_raw_signal_integrity_verified", True),
    ("source_conditions_per_asset_verified", True),
    ("physical_healthy_asset_ids", ["K007"]),
])
def test_invented_kaist_compatibility_or_provenance_cannot_be_approved(field, value):
    document = copy.deepcopy(_inventory())
    source = next(x for x in document["candidates"]
                  if x["source_id"] == "kaist_varying_load")
    source[field] = value
    with pytest.raises(SourceReadinessError):
        _validate_fixed_source_inventory(document)


def test_injecting_new_source_or_duplicate_fails_source_inventory_review():
    doc = _inventory()
    doc["candidates"].append(copy.deepcopy(doc["candidates"][-1]))
    with pytest.raises(SourceReadinessError):
        _validate_fixed_source_inventory(doc)


def test_metadata_assessment_is_never_new_independent_healthy_validation():
    candidate = copy.deepcopy(_inventory()["candidates"][1])
    candidate.update({
        "physical_healthy_asset_ids": ["UNKNOWN-NEW-1"],
        "independent_physical_asset_inventory_verified": True,
        "source_archive_integrity_verified": True,
        "source_raw_signal_integrity_verified": True,
        "source_conditions_per_asset_verified": True,
        "other_domain_equivalence_reviewed": True,
        "nominal_sample_rate_vibration_hz": 64000,
        "nominal_sample_rate_current_hz": 64000,
        "operating_condition_count": 4,
        "matched_paderborn_condition_protocol": True,
    })
    # Even a future all-green metadata checklist cannot substitute for
    # independently reviewed ORIGINAL recordings and new blind results.
    result = assess_source_metadata(candidate)
    assert result["direct_frozen_model_prediction_allowed"] is False
    assert "actual_independent_normal_evaluation_not_performed" in result["blocking_reasons"]


def test_external_research_report_no_overwrite_and_no_unapproved_ml_load(tmp_path):
    status = assess_inventory()
    outfile = tmp_path / "healthy_readiness.json"
    outfile.write_text(json.dumps(status), encoding="utf-8")
    assert status["source_metadata_not_original_recording_evidence"] is True
    assert not any(x.get("score") for x in status["results"])
    assert load_validated_model() is None



def test_railway_phm24_64k_both_sensors_is_still_unproven_as_paderborn_normal():
    row = next(r for r in _inventory()["candidates"]
               if r["source_id"] == "phm24_bjtu_rao_bogie")
    assert row["nominal_sample_rate_vibration_hz"] == 64000
    assert row["nominal_sample_rate_current_hz"] == 64000
    assert row["operating_condition_count"] == 9
    assert row["matched_paderborn_condition_protocol"] is False
    assert row["original_download_and_usage_terms_verified"] is False
    assert row["physical_healthy_asset_ids"] is None
    assert row["license"] == "not_verified_for_source_data"
    assert row["original_publisher_download_link_documented"] is True
    assert row["actual_files_downloaded_and_verified"] is False
    assert row["original_publisher_distribution_url"].startswith(
        "https://drive.google.com/drive/folders/")
    result = {x["source_id"]: x for x in assess_inventory()["results"]}[
        "phm24_bjtu_rao_bogie"
    ]
    assert result["direct_frozen_model_prediction_allowed"] is False
    assert "four_paderborn_operating_conditions_not_equivalent" in result["blocking_reasons"]
    assert "phm24_and_bjtu_rao_benchmark_overlap_not_audited" in result["blocking_reasons"]
    assert "source_data_usage_license_and_release_access_unverified" in result["blocking_reasons"]
    assert "vibration_sampling_rate_differs_from_paderborn_64khz" not in result["blocking_reasons"]
    assert "current_sampling_rate_differs_from_paderborn_64khz" not in result["blocking_reasons"]


@pytest.mark.parametrize("field,fake", [
    ("nominal_sample_rate_vibration_hz", 25600),
    ("operating_condition_count", 4),
    ("matched_paderborn_condition_protocol", True),
    ("license", "CC BY 4.0"),
    ("physical_healthy_asset_ids", ["UNPROVEN-NEW"]),
    ("independent_physical_asset_inventory_verified", True),
    ("source_archive_integrity_verified", True),
    ("source_raw_signal_integrity_verified", True),
    ("other_domain_equivalence_reviewed", True),
    ("original_download_and_usage_terms_verified", True),
    ("additional_evidence_url", "https://malicious.example"),
    ("original_publisher_download_link_documented", False),
    ("original_publisher_document", "https://untrusted.invalid"),
    ("original_publisher_distribution_url", "https://untrusted.invalid/drive"),
    ("alternative_publisher_distribution_url", "https://untrusted.invalid/baidu"),
    ("actual_files_downloaded_and_verified", True),
])
def test_phm24_public_metadata_cannot_fabricate_origins_or_originals(field, fake):
    doc = copy.deepcopy(_inventory())
    row = next(r for r in doc["candidates"]
               if r["source_id"] == "phm24_bjtu_rao_bogie")
    row[field] = fake
    with pytest.raises(SourceReadinessError):
        _validate_fixed_source_inventory(doc)


def test_phm24_or_kaist_public_sources_never_yield_new_normal_specificity():
    data = assess_inventory()
    assert data["new_healthy_bearings_validated"] == 0
    assert data["false_positive_rate_measured"] is False
    assert data["overall_accuracy_measured"] is False
    assert data["ml_predictions_performed"] is False
    assert len(data["results"]) == 4
    assert all(not row["new_independent_healthy_qualification"] for row in data["results"])
