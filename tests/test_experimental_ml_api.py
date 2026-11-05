"""Research-only 80-MAT feature upload scores the *frozen* model in the app.

Unit fixtures are SYNTHETIC. Original sensor-data scoring is separately
established by the Windows real-RAR 80-MAT CI job, not these unit tests.
"""
from __future__ import annotations

import copy
import json

import pytest
from fastapi.testclient import TestClient

from faultmate.app import app
from faultmate.integration.ml import load_validated_model
from scripts import run_experimental_paderborn_ml as experiment
from test_experimental_paderborn_real_inference import fake_source_feature_report


def test_full_synthetic_80_rec_json_to_app_frozen_research_model_score():
    fixture = fake_source_feature_report()
    offline = experiment.score_original_feature_report(fixture)
    with TestClient(app) as client:
        res = client.post("/api/ml/experimental-unitless-report", json=fixture)
        assert res.status_code == 200
        assert "no-store" in res.headers["cache-control"]
    result = res.json()
    assert result["status"] == "experimental_unapproved"
    assert result["research_inference_performed"] is True
    assert result["input_recordings"] == 80
    assert result["unique_signal_pairs_reported"] == 80
    assert result["frozen_model_sha256"] == offline["frozen_model_sha256"]
    assert result["experimental_damage_model_score"] == offline["experimental_damage_model_score"]
    assert result["experimental_predicted_label"] == offline["experimental_predicted_label"]
    assert result["uploaded_metadata_is_original_provenance_proof"] is False
    assert result["source_archive_reverified_from_original_bytes_this_http_request"] is False
    assert result["new_healthy_specificity_measured"] is False
    assert result["field_accuracy_measured"] is False
    assert result["model_approved_for_runtime"] is False
    assert result["confirmed_fault"] is False
    assert result["safe_to_work"] is False
    assert load_validated_model() is None


def test_research_report_does_not_activate_existing_si_feature_csv_route():
    with TestClient(app) as client:
        csv = (
            b"asset_id,trial_id,source_id,vibration_rms_m_s2,"
            b"vibration_peak_m_s2,current_rms_a\n"
            b"K001,T1,paderborn-bearing-datacenter,1.0,2.0,0.5\n"
        )
        r = client.post("/api/ml/inspect", content=csv,
                        headers={"content-type": "text/csv"})
    assert r.status_code == 200
    result = r.json()
    assert result["status"] == "unavailable"
    assert result["inference_performed"] is False
    assert result["confirmed_fault"] is False


@pytest.mark.parametrize("transform", [
    lambda d: d.update({"bearing_id": "FAKE1000"}),
    lambda d: d["records"].pop(),
    lambda d: d["records"][0].update({"source_raw_signal_fingerprint": "fake"}),
    lambda d: d["records"][0].update({"values": [1, 2]}),
    lambda d: d.update({"approved_for_runtime": True}),
    lambda d: d.update({"raw_si_units_verified": True}),
    lambda d: d.update({"archive_verified": False}),
    lambda d: d.update({"official_archive_md5": "f" * 32}),
])
def test_malformed_or_forged_experimental_report_never_generates_prediction(transform):
    data = fake_source_feature_report()
    transform(data)
    with TestClient(app) as client:
        r = client.post("/api/ml/experimental-unitless-report", json=data)
    assert r.status_code == 200
    result = r.json()
    assert result["status"] == "unsupported_input"
    assert result["research_inference_performed"] is False
    assert result["confirmed_fault"] is False
    assert result["safe_to_work"] is False
    assert "experimental_damage_model_score" not in result


def test_json_body_size_and_type_guard():
    with TestClient(app) as client:
        invalid = client.post(
            "/api/ml/experimental-unitless-report",
            content=b"not json", headers={"content-type": "text/plain"})
        over = client.post(
            "/api/ml/experimental-unitless-report",
            content=b"a" * 512001, headers={"content-type": "application/json"})
        empty = client.post(
            "/api/ml/experimental-unitless-report",
            content=b"", headers={"content-type": "application/json"})
    assert invalid.status_code == 415
    assert over.status_code == 413
    assert empty.status_code == 200
    assert empty.json()["research_inference_performed"] is False


def test_untrusted_browser_origin_cannot_invoke_experimental_research_post():
    with TestClient(app) as client:
        r = client.post(
            "/api/ml/experimental-unitless-report",
            json=fake_source_feature_report(),
            headers={"Origin": "http://attacker.example"})
    assert r.status_code == 403
    assert r.json()["detail"] == "local_same_origin_required"


def test_cli_original_extractor_can_export_80_feature_json_for_local_ui(
        tmp_path, monkeypatch):
    original = tmp_path / "K001.rar"
    original.write_bytes(b"fake only - actual RAR tested in source CI")
    feature = tmp_path / "features.json"
    monkeypatch.setattr(experiment, "extract_archive",
                        lambda *_args, **_kwargs: fake_source_feature_report())
    score = experiment.run_archive(original, "K001", sevenzip="MOCK7Z",
                                   features_out=feature)
    assert score["source_archive_verified_from_original_bytes_same_run"] is True
    assert feature.is_file()
    with TestClient(app) as client:
        result = client.post(
            "/api/ml/experimental-unitless-report",
            content=feature.read_bytes(),
            headers={"content-type": "application/json"}).json()
    assert result["research_inference_performed"] is True
    assert result["experimental_damage_model_score"] == score["experimental_damage_model_score"]
    assert result["source_archive_reverified_from_original_bytes_this_http_request"] is False
    preserved = feature.read_bytes()
    with pytest.raises(ValueError, match="research_features_output_already_exists"):
        experiment.run_archive(original, "K001", sevenzip="MOCK7Z", features_out=feature)
    assert feature.read_bytes() == preserved
