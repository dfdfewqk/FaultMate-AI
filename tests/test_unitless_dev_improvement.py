"""Safety and regression tests for the dev-only bearing aggregation study.

Fixtures use synthetic numbers and fake recorded SHA values ONLY to exercise
code paths. Their accuracy is not a Paderborn result or a model approval.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from scripts.audit_paderborn_assets import CATALOG, OFFICIAL_CONDITIONS, validate_catalog
from scripts.extract_paderborn_unitless import SCHEMA, FEATURE_NAMES
from scripts.evaluate_unitless_dev_only import (
    BASELINE_REPORT_SHA256, CANDIDATES, PREVIOUSLY_OPENED_TEST_BEARINGS,
    _predict, analyze_development, verified_dev_rows,
)


def make_fixture(tmp_path):
    features = tmp_path / "features"
    audits = tmp_path / "audits"
    features.mkdir()
    audits.mkdir()
    catalog = {x["id"]: x for x in validate_catalog(json.loads(
        CATALOG.read_text(encoding="utf-8")))}
    dev = ["K001", "K002", "K003", "K004", "K005",
           "KA04", "KA16", "KB23", "KI04", "KI16"]
    sealed = ["K006", "KI18"]
    rng = np.random.RandomState(123)
    hashes = []
    for asset in sorted(dev):
        label = catalog[asset]["label"]
        records, source_records, local_first, duplicate_list = [], [], {}, []
        for condition in sorted(OFFICIAL_CONDITIONS):
            for trial in range(1, 21):
                name = f"{condition}_{asset}_{trial}.mat"
                # Test provenance logic, not real KA04 signal values.
                duplicate = (asset == "KA04" and condition == "N09_M07_F10"
                             and trial in (17, 18, 19, 20))
                first_name = f"{condition}_KA04_1.mat" if duplicate else None
                fingerprint = hashlib.sha256(
                    (first_name or name).encode("utf-8")).hexdigest()
                assert fingerprint not in local_first or duplicate
                local_first.setdefault(fingerprint, name)
                mat_sha = hashlib.sha256((name + "MAT").encode()).hexdigest()
                fake_values = (
                    list(rng.normal(loc=1 + 3 * (label == "damaged"),
                                    scale=.02, size=12))
                    if not duplicate else None
                )
                row = {
                    "recording": name, "condition": condition, "trial": trial,
                    "source_mat_sha256": mat_sha,
                    "source_raw_signal_fingerprint": fingerprint,
                    "sample_count": 100000, "duplicate_of": first_name,
                    "values": fake_values,
                }
                records.append(row)
                source_records.append({
                    "recording": name, "condition": condition, "trial": trial,
                    "mat_sha256": mat_sha, "raw_signal_fingerprint": fingerprint,
                    "sample_count": 100000, "duplicate_of": first_name,
                })
                if duplicate:
                    duplicate_list.append({"recording": name, "duplicate_of": first_name})
        feat = {
            "schema": SCHEMA, "bearing_id": asset,
            "status": "real_raw_unitless_features_unreviewed",
            "dataset": "paderborn_bearing_datacenter",
            "label": label, "license": "CC BY-NC 4.0",
            "source_catalog_sha256": hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
            "official_archive_md5": catalog[asset]["md5"],
            "archive_verified": True,
            "raw_si_units_verified": False,
            "si_amplitudes_used": False,
            "approved_for_runtime": False,
            "feature_names": list(FEATURE_NAMES),
            "source_recording_count": 80,
            "unique_recording_count": 80 - len(duplicate_list),
            "records": records, "duplicates": duplicate_list,
        }
        audit = {
            "bearing_id": asset, "label": label,
            "source_md5_verified": True,
            "source_archive_md5": catalog[asset]["md5"],
            "source_catalog_sha256": hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
            "raw_units_verified": False,
            "approved_for_training": False,
            "inspected_recordings": 80, "recordings": source_records,
            "duplicate_raw_recordings": duplicate_list,
        }
        fp = features / f"{asset}.json"
        ap = audits / f"{asset}.json"
        fp.write_text(json.dumps(feat), encoding="utf-8")
        ap.write_text(json.dumps(audit), encoding="utf-8")
        hashes.append({
            "bearing_id": asset,
            "feature_report_sha256": hashlib.sha256(fp.read_bytes()).hexdigest(),
            "raw_audit_sha256": hashlib.sha256(ap.read_bytes()).hexdigest(),
        })
    hashes.extend({"bearing_id": b, "feature_report_sha256": "x" * 64,
                   "raw_audit_sha256": "y" * 64} for b in sealed)
    report = {
        "status": "real_source_experimental_training_finished_no_runtime_approval",
        "ml_model_approved": False, "feature_schema": SCHEMA,
        "provenance": {
            "source_bearings": 12, "source_recordings": 960,
            "unique_recordings": 956, "duplicates_dropped": 4,
            "physical_si_units_verified": False,
            "license": "CC BY-NC 4.0",
            "source_audit_sha256": hashes,
        },
        "independent_split": {
            "train": ["K001", "K003", "K004", "K005",
                      "KA04", "KA16", "KB23", "KI16"],
            "validation": ["K002", "KI04"], "test": sealed,
        },
    }
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(report), encoding="utf-8")
    baseline_sha = hashlib.sha256(baseline.read_bytes()).hexdigest()
    return features, audits, baseline, baseline_sha


def _verified_fixture(tmp_path):
    f, a, b, digest = make_fixture(tmp_path)
    return verified_dev_rows(f, a, b, baseline_sha256=digest)


def test_original_baseline_digest_is_pinned_to_real_ci_run():
    assert len(BASELINE_REPORT_SHA256) == 64
    assert BASELINE_REPORT_SHA256 != "0" * 64
    assert PREVIOUSLY_OPENED_TEST_BEARINGS == {"K006", "KI18"}


def test_ten_dev_bearings_only_excludes_opened_test_assets(tmp_path):
    rows, provenance = _verified_fixture(tmp_path)
    assert len(rows) == 796
    assert provenance["unique_recordings"] == 796
    assert provenance["duplicate_exclusions"] == 4
    assert len(provenance["dev_assets"]) == 10
    assert not set(provenance["dev_assets"]).intersection(
        PREVIOUSLY_OPENED_TEST_BEARINGS)
    assert set(provenance["test_asset_ids_excluded"]) == PREVIOUSLY_OPENED_TEST_BEARINGS


def test_extra_heldout_feature_json_fails_closed(tmp_path):
    f, a, b, digest = make_fixture(tmp_path)
    (f / "K006.json").write_text("{}")
    with pytest.raises(ValueError, match="no_test_bearings"):
        verified_dev_rows(f, a, b, baseline_sha256=digest)


def test_source_fingerprint_changed_after_baseline_fails_closed(tmp_path):
    f, a, b, digest = make_fixture(tmp_path)
    p = f / "K001.json"
    d = json.loads(p.read_text())
    d["records"][0]["source_raw_signal_fingerprint"] = "f" * 64
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="blob_sha_mismatch"):
        verified_dev_rows(f, a, b, baseline_sha256=digest)


def test_any_unpinned_prior_result_rejected(tmp_path):
    f, a, b, _ = make_fixture(tmp_path)
    with pytest.raises(ValueError, match="baseline_real_source_evaluation_hash_mismatch"):
        verified_dev_rows(f, a, b)


def test_four_fixed_candidate_methods_are_dimensionless_and_experimental(tmp_path):
    rows, provenance = _verified_fixture(tmp_path)
    report, model = analyze_development(rows, provenance)
    assert list(report["development_only_lobo"]) == [x[0] for x in CANDIDATES]
    assert report["nested_development_selection"]["metrics"]["physical_bearings"] == 10
    assert len(report["per_condition_robustness"]) == 4
    assert report["new_independent_external_evaluation"] is False
    assert report["previously_opened_heldout_reused"] is False
    assert report["production_approved"] is False
    assert model["approved_for_runtime"] is False
    assert model["runtime_inference_compatible"] is False
    assert model["source_numeric_si_units_verified"] is False
    assert len(model["feature_names"]) == 12
    assert set(model["training_asset_ids"]).isdisjoint(
        PREVIOUSLY_OPENED_TEST_BEARINGS)


def test_any_fit_on_same_heldout_bearing_rejected(tmp_path):
    rows, provenance = _verified_fixture(tmp_path)
    assets = provenance["dev_assets"]
    with pytest.raises(ValueError, match="evaluation_asset_leakage"):
        _predict(rows, assets, assets[0], CANDIDATES[1])


def test_committed_real_dev_model_exactly_matches_successful_actions_artifact():
    # SHA256 of development_aggregated_unapproved.json in real run 41969444944.
    # Prevent hand-transcription errors or quietly swapping research coefficients.
    p = (CATALOG.parents[1] / "docs" / "experiments" /
         "PADERBORN_BEARING_AGGREGATED_UNAPPROVED_20261105.json")
    exact_bytes = p.read_bytes()
    assert hashlib.sha256(exact_bytes).hexdigest() == (
        "84a7c059fa769d1b0e2bd0075ecba92bcd06ae24acf961e0ea2120d9d44a0ab0"
    )
    data = json.loads(exact_bytes)
    assert data["status"] == "experimental_unapproved_not_for_runtime"
    assert data["approved_for_runtime"] is False
    assert data["runtime_inference_compatible"] is False
    assert data["source_numeric_si_units_verified"] is False
    assert set(data["training_asset_ids"]).isdisjoint(PREVIOUSLY_OPENED_TEST_BEARINGS)
