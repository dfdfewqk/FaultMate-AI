"""Stage 4 alternative: unitless Paderborn experiment software tests only.

Synthetic arrays and synthetic "source reports" are used here solely to test
the gate. They never count as actual measured data, nor as real training scores.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from scripts.audit_paderborn_assets import CATALOG, OFFICIAL_CONDITIONS, validate_catalog
from scripts.extract_paderborn_unitless import (
    FEATURE_NAMES, SCHEMA, shape_features, record_features,
)
from scripts.train_paderborn_unitless import (
    load_verified_unitless_cohort, independent_split, _metrics,
    train_real_unitless,
)


def test_shapes_are_dimensionless_under_gain_and_constant_offset():
    rng = np.random.RandomState(121)
    signal = rng.normal(size=16384)
    a = shape_features(signal)
    b = shape_features(signal * 2.73 + 13.7)
    assert len(a) == 6
    assert np.allclose(a, b, atol=2e-10, rtol=1e-9)
    assert np.all(np.isfinite(a))
    features = record_features(signal, signal * 1.7 - 40)
    assert len(features) == len(FEATURE_NAMES) == 12


def test_constant_invalid_or_short_signals_fail():
    with pytest.raises(ValueError):
        shape_features(np.zeros(16384))
    with pytest.raises(ValueError):
        shape_features(np.arange(1000))
    with pytest.raises(ValueError):
        shape_features(np.ones(16384) * np.nan)


def build_fake_manifest_cohort(root):
    feature_dir, audit_dir = root / "synthetic_features", root / "synthetic_audits"
    feature_dir.mkdir()
    audit_dir.mkdir()
    assets = validate_catalog(json.loads(CATALOG.read_text(encoding="utf-8")))
    cat_sha = hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    for idx, asset in enumerate(assets):
        name, label = asset["id"], asset["label"]
        features = []
        raw = []
        known = []
        for condition in sorted(OFFICIAL_CONDITIONS):
            for trial in range(1, 21):
                recording = f"{condition}_{name}_{trial}.mat"
                # One synthetic fake feature is a duplicate of the earliest
                # file in four KA04 locations (mimics expected source cardinality).
                dupes = {
                    "N09_M07_F10_KA04_18.mat": "N09_M07_F10_KA04_17.mat",
                    "N15_M07_F04_KA04_15.mat": "N15_M07_F04_KA04_6.mat",
                    "N15_M07_F04_KA04_19.mat": "N15_M07_F04_KA04_5.mat",
                    "N15_M07_F04_KA04_20.mat": "N15_M07_F04_KA04_6.mat",
                }
                prior = dupes.get(recording)
                signal = hashlib.sha256((prior or recording).encode()).hexdigest()
                mat_sha = hashlib.sha256(recording.encode()).hexdigest()
                values = ([float(idx + trial / 100), float(idx * 2.3),
                           2., 3., .4, .1, 2., 3., 4., .5, .6, .7]
                          if prior is None else None)
                features.append({
                    "recording": recording, "condition": condition, "trial": trial,
                    "source_mat_sha256": mat_sha, "source_raw_signal_fingerprint": signal,
                    "sample_count": 256000, "duplicate_of": prior, "values": values,
                })
                raw.append({
                    "recording": recording, "condition": condition, "trial": trial,
                    "mat_sha256": mat_sha, "raw_signal_fingerprint": signal,
                    "sample_count": 256000, "duplicate_of": prior,
                })
        duplicates = [{"recording": r["recording"], "duplicate_of": r["duplicate_of"]}
                      for r in features if r["duplicate_of"]]
        f = {
            "schema": SCHEMA, "status": "real_raw_unitless_features_unreviewed",
            "dataset": "paderborn_bearing_datacenter", "bearing_id": name,
            "label": label, "license": "CC BY-NC 4.0",
            "official_archive_md5": asset["md5"], "archive_verified": True,
            "source_catalog_sha256": cat_sha,
            "raw_si_units_verified": False, "si_amplitudes_used": False,
            "approved_for_runtime": False, "feature_names": FEATURE_NAMES,
            "records": features, "source_recording_count": 80,
            "unique_recording_count": 80 - len(duplicates),
            "duplicates": duplicates,
        }
        a = {
            "bearing_id": name, "label": label,
            "source_md5_verified": True, "source_archive_md5": asset["md5"],
            "inspected_recordings": 80, "raw_units_verified": False,
            "approved_for_training": False,
            "duplicate_raw_recordings": duplicates,
            "recordings": raw,
        }
        (feature_dir / f"{name}.json").write_text(json.dumps(f), encoding="utf-8")
        (audit_dir / f"{name}.json").write_text(json.dumps(a), encoding="utf-8")
    return feature_dir, audit_dir


def test_all_12_asset_shas_matched_and_duplicate_raw_records_excluded(tmp_path):
    feature_dir, audit_dir = build_fake_manifest_cohort(tmp_path)
    rows, metadata = load_verified_unitless_cohort(feature_dir, audit_dir)
    assert len(rows) == 956
    assert metadata["duplicates_dropped"] == 4
    assert metadata["physical_si_units_verified"] is False
    assert {r["asset_id"] for r in rows} == {
        x["id"] for x in validate_catalog(json.loads(CATALOG.read_text()))}
    split = independent_split(rows)
    assert len(split["train"]) == 8
    assert len(split["validation"]) == 2
    assert len(split["test"]) == 2
    assert not set(split["train"]) & set(split["test"])
    assert not set(split["validation"]) & set(split["test"])
    assert {x for x in split["test"] if x.startswith("K0")}.__len__() == 1


def test_source_raw_sha_tamper_blocks_experimental_training(tmp_path):
    feature_dir, audit_dir = build_fake_manifest_cohort(tmp_path)
    path = feature_dir / "K001.json"
    doc = json.loads(path.read_text())
    doc["records"][0]["source_mat_sha256"] = "f" * 64
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="original_signal_provenance_mismatch"):
        load_verified_unitless_cohort(feature_dir, audit_dir)


def test_fake_class_label_tampering_blocks_training(tmp_path):
    feature_dir, audit_dir = build_fake_manifest_cohort(tmp_path)
    path = feature_dir / "KA04.json"
    doc = json.loads(path.read_text())
    doc["label"] = "healthy"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="provenance_invalid"):
        load_verified_unitless_cohort(feature_dir, audit_dir)


def test_unverified_and_incomplete_cohorts_fail_closed(tmp_path):
    feature_dir, audit_dir = build_fake_manifest_cohort(tmp_path)
    (feature_dir / "KI18.json").unlink()
    with pytest.raises(ValueError, match="all_12_feature_reports"):
        load_verified_unitless_cohort(feature_dir, audit_dir)


def test_experimental_model_from_synthetic_fixture_stays_unapproved(tmp_path):
    feature_dir, audit_dir = build_fake_manifest_cohort(tmp_path)
    dest = tmp_path / "software_test_only"
    report = train_real_unitless(feature_dir, audit_dir, dest)
    assert report["ml_model_approved"] is False
    assert report["external_field_generalization_demonstrated"] is False
    assert report["sealed_test"]["metrics"]["independent_bearing_count"] == 2
    assert report["development_leave_one_bearing_out"]["metrics"]["independent_bearing_count"] == 10
    model = json.loads((dest / "experimental_unapproved_model.json").read_text())
    assert model["not_a_validated_model"] is True
    assert model["no_runtime_activation"] is True
    assert model["source_numeric_si_units_verified"] is False
    assert not (dest / "bearing_validated.json").exists()
    with pytest.raises(ValueError, match="output_folder_exists"):
        train_real_unitless(feature_dir, audit_dir, dest)
