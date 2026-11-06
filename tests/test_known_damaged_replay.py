"""Previously tested damaged bearings: frozen-model replay and known KI21 miss.

ALL inputs here are SYNTHETIC feature records. They only validate the API,
not scientific sensitivity. The real original KI21 MD5/80 MAT is separately
replayed in GitHub Windows CI without refitting or changing the old test.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from scripts import replay_prior_damaged_bearing as replay
from scripts.evaluate_unseen_paderborn_damaged import frozen_coefficients
from scripts.extract_unseen_paderborn_damaged import (
    KNOWN_NEW_MD5, MANIFEST, PINNED_MODEL_SHA, canonical_json_sha256,
)
from test_experimental_paderborn_real_inference import fake_source_feature_report
from faultmate.integration import research_raw_archive as raw


def fake_historically_opened_damaged_report(asset="KI21", *, miss=True):
    base = fake_source_feature_report("K001")
    model = frozen_coefficients()
    sign = np.sign(model["coefs"])
    # Artificial extreme to test both score directions, NOT real measurements.
    direction = -14.0 if miss else 14.0
    vector = (model["mean"] + direction * model["scale"] * sign).tolist()
    for rec in base["records"]:
        rec["recording"] = rec["recording"].replace("K001", asset)
        rec["values"] = list(vector)
    base.update({
        "bearing_id": asset, "label": "damaged",
        "evaluation_role": "never_seen_damaged_only",
        "status": "real_original_unseen_damaged_features_unapproved",
        "source_model_sha256": PINNED_MODEL_SHA,
        "source_manifest_sha256": canonical_json_sha256(MANIFEST),
        "label_source": "Lessmeier et al. (2016), Table 5",
        "damage_origin": "accelerated_lifetime",
        "official_archive_md5": KNOWN_NEW_MD5[asset],
    })
    return base


def test_fake_known_ki21_missed_damaged_is_not_relabelled_safe_or_new_accuracy():
    data = fake_historically_opened_damaged_report()
    vector, info = replay.validate_prior_damaged_report(data)
    assert vector.shape == (12,)
    assert info["physical_truth_label"] == "damaged"
    result = replay.score_prior_damaged_report(data)
    assert result["bearing_id"] == "KI21"
    assert result["physical_truth_label"] == "damaged"
    assert result["experimental_predicted_label"] == "healthy"
    assert result["historical_false_negative"] is True
    assert result["experimental_damage_model_score"] < .5
    assert result["new_independent_damaged_or_healthy_test_performed"] is False
    assert result["independent_healthy_specificity_measured"] is False
    assert result["field_safety_or_fault_confirmation"] is False
    assert result["model_runtime_approved"] is False
    assert result["frozen_model_sha256"] == PINNED_MODEL_SHA


def test_fake_previously_tested_damaged_can_score_positive_without_new_test_claim():
    r = replay.score_prior_damaged_report(
        fake_historically_opened_damaged_report("KA15", miss=False))
    assert r["physical_truth_label"] == "damaged"
    assert r["experimental_predicted_label"] == "damaged"
    assert r["historical_false_negative"] is False
    assert r["new_independent_damaged_or_healthy_test_performed"] is False


@pytest.mark.parametrize("mutation", [
    lambda d: d.update({"bearing_id": "K001"}),
    lambda d: d.update({"source_manifest_sha256": "0"*64}),
    lambda d: d.update({"source_model_sha256": "0"*64}),
    lambda d: d.update({"label": "healthy"}),
    lambda d: d.update({"official_archive_md5": "0"*32}),
    lambda d: d.update({"approved_for_runtime": True}),
    lambda d: d.update({"raw_si_units_verified": True}),
    lambda d: d.update({"source_recording_count": 79}),
    lambda d: d["records"].pop(),
    lambda d: d["records"][0].update({"condition": "invalid"}),
    lambda d: d["records"][0].update({"trial": 2}),
    lambda d: d["records"][0].update({"recording": "../../unsafe.mat"}),
    lambda d: d["records"][0].update({"source_mat_sha256": "fake"}),
    lambda d: d["records"][0].update({"source_raw_signal_fingerprint": "fake"}),
    lambda d: d["records"][0].update({"values": [1.0] * 3}),
    lambda d: d["records"][0].update({"values": [math.nan] * 12}),
    lambda d: d["records"][0].update({"values": [True] * 12}),
    lambda d: d["records"][0].update({"duplicate_of": "fake.mat"}),
    lambda d: d.update({"unique_recording_count": 79}),
])
def test_forged_or_incomplete_damaged_source_never_scores(mutation):
    data = fake_historically_opened_damaged_report()
    mutation(data)
    with pytest.raises((ValueError, TypeError, KeyError)):
        replay.score_prior_damaged_report(data)


def test_historical_ki21_expected_miss_must_not_silently_flip_to_success():
    data = fake_historically_opened_damaged_report("KI21", miss=False)
    with pytest.raises(ValueError, match="KI21_historical_false_negative_not_reproduced"):
        replay.score_prior_damaged_report(data)


def test_prior_damaged_original_archive_route_uses_original_extractor_only(
        monkeypatch, tmp_path):
    archive = tmp_path / "KI21.rar"
    archive.write_bytes(b"SYNTHETIC_NOT_A_REAL_RAR")
    called = []

    def fake_original_extractor(path, asset, *, sevenzip):
        called.append((path, asset, sevenzip))
        return fake_historically_opened_damaged_report(asset)

    monkeypatch.setattr(replay, "extract_unseen", fake_original_extractor)
    r = replay.run_prior_damaged_archive(archive, "KI21", sevenzip="fake-7zip")
    assert called == [(archive.absolute(), "KI21", "fake-7zip")]
    assert r["original_rar_md5_verified_in_this_run"] is True
    assert r["original_real_80_mat_rechecked_this_run"] is True
    assert r["historical_false_negative"] is True
    # These two booleans above are only true for a real extractor in
    # production. This unit mock provides no original sensor evidence.


def test_unregistered_or_original_training_asset_cannot_impersonate_prior_damaged(
        tmp_path):
    archive = tmp_path / "K001.rar"
    archive.write_bytes(b"fake")
    with pytest.raises(ValueError, match="not_one_of_eight"):
        replay.run_prior_damaged_archive(archive, "K001", sevenzip="7z")


def test_direct_archive_endpoint_identifies_historical_miss_in_research_result(
        monkeypatch, tmp_path):
    # Tests result formatting only: NO real source or independent test implied.
    monkeypatch.setattr(raw.shutil, "which", lambda _name: "mock-7zip")
    monkeypatch.setattr(
        replay, "run_prior_damaged_archive",
        lambda *_args, **_kwargs: replay.score_prior_damaged_report(
            fake_historically_opened_damaged_report("KI21")),
    )
    result = raw._research_score(tmp_path / "KI21.rar", "KI21")
    assert result["status"] == "experimental_unapproved"
    assert result["bearing_id"] == "KI21"
    assert result["source_known_research_truth_label"] == "damaged"
    assert result["experimental_predicted_label"] == "healthy"
    assert result["historical_known_damaged_false_negative"] is True
    assert result["previously_opened_damaged_test_replay_not_new_evaluation"] is True
    assert result["old_training_bearing_may_have_been_used"] is False
    assert "미탐" in result["message"]
    assert result["new_independent_healthy_specificity_measured"] is False
    assert result["model_approved_for_runtime"] is False
    assert result["safe_to_work"] is False


def test_20_documented_assets_allowed_but_unsupported_new_asset_denied():
    old = raw.validate_bearing_id("K001")
    known_miss = raw.validate_bearing_id("KI21")
    assert old == "K001"
    assert known_miss == "KI21"
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as err:
        raw.validate_bearing_id("KI22")
    assert err.value.status_code == 422
