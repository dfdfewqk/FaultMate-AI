"""Research bearing ML pipeline guards. All fixtures SYNTHETIC, not measured."""
from __future__ import annotations

import copy
import hashlib
import json
import math

import numpy as np
import pytest

from scripts.audit_paderborn_assets import CATALOG, OFFICIAL_CONDITIONS, validate_catalog
from scripts.extract_paderborn_unitless import FEATURE_NAMES, SCHEMA
from scripts.evaluate_unseen_paderborn_damaged import frozen_coefficients
from scripts import run_experimental_paderborn_ml as exp


def fake_source_feature_report(bearing="K001", duplicate_first=False):
    """Synthetic feature vectors only: the real original RAR is tested in CI."""
    catalog = {x["id"]: x for x in validate_catalog(json.loads(CATALOG.read_text()))}
    model = frozen_coefficients()
    records = []
    duplicates = []
    first = None
    for cond in sorted(OFFICIAL_CONDITIONS):
        for trial in range(1, 21):
            name = f"{cond}_{bearing}_{trial}.mat"
            dup = bool(duplicate_first and len(records) == 1)
            fingerprint = hashlib.sha256(
                (first if dup else name).encode()
            ).hexdigest()
            if first is None:
                first = name
            values = [float(z) for z in model["mean"]] if not dup else None
            records.append({
                "condition": cond, "trial": trial, "recording": name,
                "source_mat_sha256": hashlib.sha256(("MAT" + name).encode()).hexdigest(),
                "source_raw_signal_fingerprint": fingerprint,
                "sample_count": 256000,
                "duplicate_of": first if dup else None,
                "values": values,
            })
            if dup:
                duplicates.append({"recording": name, "duplicate_of": first})
    return {
        "schema": SCHEMA, "status": "real_raw_unitless_features_unreviewed",
        "dataset": "paderborn_bearing_datacenter", "bearing_id": bearing,
        "label": catalog[bearing]["label"],
        "official_archive_md5": catalog[bearing]["md5"],
        "license": "CC BY-NC 4.0", "archive_verified": True,
        "raw_si_units_verified": False, "si_amplitudes_used": False,
        "ml_trained": False, "approved_for_runtime": False,
        "feature_names": list(FEATURE_NAMES),
        "source_recording_count": 80,
        "unique_recording_count": 80 - int(duplicate_first),
        "duplicates": duplicates, "records": records,
    }


def test_synthetic_full_80_record_12_feature_pipeline_uses_original_frozen_coefficients():
    doc = fake_source_feature_report()
    v, meta = exp.aggregate_verified_feature_report(doc)
    model = frozen_coefficients()
    assert v.shape == (12,)
    assert np.allclose(v, model["mean"], atol=0, rtol=0)
    assert meta["source_records"] == 80
    result = exp.score_original_feature_report(doc)
    expected = 1 / (1 + math.exp(-model["intercept"]))
    assert result["experimental_damage_model_score"] == round(expected, 8)
    assert result["experimental_predicted_label"] == "damaged"  # synthetic mean
    assert result["runtime_ml_model_approved"] is False
    assert result["independent_heldout_healthy_specificity_measured"] is False
    assert result["confirmed_fault"] is False
    assert result["safe_to_work"] is False
    assert result["result_may_include_previously_trained_bearing"] is True


def test_synthetic_ka04_duplicate_signal_is_excluded_not_counted_as_second_measurement():
    doc = fake_source_feature_report("KA04", duplicate_first=True)
    vector, meta = exp.aggregate_verified_feature_report(doc)
    assert len(vector) == len(FEATURE_NAMES)
    assert meta["source_records"] == 80
    assert meta["unique_signal_pairs"] == 79
    assert meta["duplicates_excluded"] == 1
    assert exp.score_original_feature_report(doc)["research_input_source"]["duplicates_excluded"] == 1


@pytest.mark.parametrize("tamper", [
    lambda d: d.update({"archive_verified": False}),
    lambda d: d.update({"approved_for_runtime": True}),
    lambda d: d.update({"label": "damaged"}),
    lambda d: d.update({"license": "CC BY 4.0"}),
    lambda d: d.update({"raw_si_units_verified": True}),
    lambda d: d.update({"official_archive_md5": "f" * 32}),
    lambda d: d.update({"bearing_id": "KA15"}),
    lambda d: d.update({"feature_names": list(reversed(d["feature_names"]))}),
    lambda d: d["records"].pop(),
    lambda d: d["records"][0].update({"condition": "N99_M99_F99"}),
    lambda d: d["records"][0].update({"trial": 2}),
    lambda d: d["records"][0].update({"sample_count": 1}),
    lambda d: d["records"][0].update({"source_raw_signal_fingerprint": "0"}),
    lambda d: d["records"][0].update({"values": [float("nan")] * 12}),
    lambda d: d["records"][0].update({"values": [1.0] * 3}),
    lambda d: d["records"][0].update({"values": [True] * 12}),
    lambda d: d["records"][0].update({"duplicate_of": "fake.mat"}),
    lambda d: d["records"][0].update({"values": None}),
    lambda d: d.update({"unique_recording_count": 79}),
    lambda d: d.update({"duplicates": [{"recording": "fake", "duplicate_of": "x"}]}),
])
def test_fake_or_incomplete_original_record_contract_never_produces_model_score(tamper):
    doc = fake_source_feature_report()
    tamper(doc)
    with pytest.raises((ValueError, TypeError)):
        exp.score_original_feature_report(doc)


def test_archive_input_is_reused_from_existing_proven_extractor(monkeypatch, tmp_path):
    source = tmp_path / "K001.rar"
    source.write_bytes(b"fake fixture never original RAR")
    called = []

    def extractor(path, bearing, *, sevenzip):
        called.append((path, bearing, sevenzip))
        return fake_source_feature_report(bearing)

    monkeypatch.setattr(exp, "extract_archive", extractor)
    r = exp.run_archive(source, "k001", sevenzip="fake-7z")
    assert called == [(source.absolute(), "K001", "fake-7z")]
    assert r["source_archive_verified_from_original_bytes_same_run"] is True
    assert r["source_mat_files_actually_read_this_run"] == 80
    assert r["new_independent_test_bearing_claimed"] is False
    assert r["runtime_ml_model_approved"] is False


def test_full_pipeline_failure_never_writes_report_or_modifies_source(monkeypatch, tmp_path):
    source = tmp_path / "K001.rar"
    source.write_bytes(b"fake source")
    dest = tmp_path / "nested" / "score.json"
    monkeypatch.setattr(exp, "run_archive",
                        lambda *_args, **_kw: (_ for _ in ()).throw(
                            ValueError("fake_original_md5_mismatch")))
    assert exp.main([
        "--archive", str(source), "--bearing-id", "K001",
        "--sevenzip", "some_7z", "--out", str(dest),
    ]) == 2
    assert not dest.exists()
    assert source.read_bytes() == b"fake source"


def test_report_output_exclusive_and_no_production_model_file_created(monkeypatch, tmp_path):
    source = tmp_path / "K001.rar"
    source.write_bytes(b"test file")
    monkeypatch.setattr(exp, "run_archive", lambda *_args, **_kw: {
        **exp.score_original_feature_report(fake_source_feature_report()),
        "source_archive_verified_from_original_bytes_same_run": True,
        "source_mat_files_actually_read_this_run": 80,
    })
    target = tmp_path / "output.json"
    args = ["--archive", str(source), "--bearing-id", "K001",
            "--sevenzip", "mock-7z", "--out", str(target)]
    assert exp.main(args) == 0
    report = json.loads(target.read_text(encoding="utf-8"))
    assert report["status"] == "experimental_model_scored_unapproved_not_for_field_use"
    original = target.read_bytes()
    assert exp.main(args) == 2
    assert target.read_bytes() == original
    from faultmate.integration.ml import load_validated_model
    assert load_validated_model() is None
