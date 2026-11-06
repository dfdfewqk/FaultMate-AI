"""Synthetic API guard tests for source RAR research-only upload.

These fixtures ARE NOT original 100MB Paderborn archives: the real-data test
is a separate official Zenodo K001 MD5 + full 80-MAT Windows CI job.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from faultmate.app import app
from faultmate.integration import research_raw_archive as original


def _request(data=b"SYNTHETIC_NOT_A_REAL_RAR" * 3, *, bearing="K001",
             content_type="application/octet-stream", origin=None):
    headers = {
        "content-type": content_type,
        "x-faultmate-bearing-id": bearing,
    }
    if origin is not None:
        headers["origin"] = origin
    with TestClient(app) as client:
        return client.post(
            "/api/ml/experimental-original-rar",
            content=data, headers=headers)


def test_original_source_streamed_to_temp_and_deleted_even_after_success(
        monkeypatch):
    monkeypatch.setattr(original, "MIN_ORIGINAL_RAR_BYTES", 12)
    seen = []

    def synthetic_worker(path: Path, bearing: str):
        assert bearing == "K001"
        assert path.name == "K001.rar"
        assert path.is_file() and not path.is_symlink()
        assert path.read_bytes() == b"SYNTHETIC_NOT_A_REAL_RAR" * 3
        seen.append(path)
        return {
            "status": "experimental_unapproved",
            "research_inference_performed": True,
            "original_rar_md5_verified_in_this_request": True,
            "source_mat_files_actually_read_this_run": 80,
            "model_approved_for_runtime": False,
            "confirmed_fault": False, "safe_to_work": False,
            "synthetic_worker_only": True,
        }

    monkeypatch.setattr(original, "_research_score", synthetic_worker)
    response = _request()
    assert response.status_code == 200
    result = response.json()
    assert result["synthetic_worker_only"] is True
    assert result["confirmed_fault"] is False
    assert result["safe_to_work"] is False
    assert len(seen) == 1
    assert not seen[0].exists()  # original temp RAR deleted


def test_small_or_missing_original_input_does_not_trigger_model(monkeypatch):
    monkeypatch.setattr(original, "_research_score",
                        lambda *_: pytest.fail("too-small RAR must never score"))
    assert _request(b"tiny").status_code == 422
    assert _request(b"").status_code in (400, 422)
    assert _request(b"tiny", bearing="KI22").status_code == 422
    assert _request(b"tiny", bearing="../K001").status_code == 422


@pytest.mark.parametrize("bearing", ["", "K777", "KI22", "../../K001", "KI99999", "K001.rar", "k001"])
def test_original_bearing_warehouse_allowlist_checked_before_stream(monkeypatch,
                                                                     bearing):
    monkeypatch.setattr(original, "_research_score",
                        lambda *_: pytest.fail("unsupported bearing scored"))
    assert _request(b"some test data", bearing=bearing).status_code == 422


def test_disallowed_content_type_and_foreign_origin_rejected(monkeypatch):
    monkeypatch.setattr(original, "_research_score",
                        lambda *_: pytest.fail("cross-site/bad MIME scored"))
    assert _request(content_type="application/json").status_code == 415
    response = _request(origin="http://evil.example")
    assert response.status_code == 403
    assert response.json()["detail"] == "local_same_origin_required"


def test_overlarge_content_length_and_stream_size_do_not_begin_processing(monkeypatch):
    monkeypatch.setattr(original, "_research_score",
                        lambda *_: pytest.fail("oversize data scored"))
    monkeypatch.setattr(original, "MAX_ORIGINAL_RAR_BYTES", 32)
    assert _request(data=b"a" * 100).status_code == 413
    with TestClient(app) as client:
        # Iterator triggers chunked content without Content-Length.
        r = client.post(
            "/api/ml/experimental-original-rar",
            content=iter([b"a" * 20, b"b" * 25]),
            headers={"content-type": "application/octet-stream",
                     "x-faultmate-bearing-id": "K001"})
    assert r.status_code == 413


def test_concurrent_original_analysis_declined_with_409(monkeypatch):
    monkeypatch.setattr(original, "MIN_ORIGINAL_RAR_BYTES", 12)
    assert original._RESEARCH_BUSY.acquire(blocking=False)
    try:
        r = _request()
        assert r.status_code == 409
        assert r.json()["detail"] == "research_archive_scoring_already_running"
    finally:
        original._RESEARCH_BUSY.release()


def test_low_temp_disk_blocks_before_writing_and_scoring(monkeypatch):
    monkeypatch.setattr(original, "MIN_ORIGINAL_RAR_BYTES", 12)
    monkeypatch.setattr(original.shutil, "disk_usage",
                        lambda *_: SimpleNamespace(free=1))
    monkeypatch.setattr(original, "_research_score",
                        lambda *_: pytest.fail("disk unavailable yet computed"))
    r = _request()
    assert r.status_code == 507


def test_original_md5_or_archive_failure_never_generates_prediction_or_leaks_path(
    monkeypatch,
):
    monkeypatch.setattr(original, "MIN_ORIGINAL_RAR_BYTES", 12)

    def failed_integrity(path, ident):
        raise ValueError(f"official_source_md5_mismatch:{path}/SECRET_PRIVATE_PATH")

    monkeypatch.setattr(original, "_research_score", failed_integrity)
    r = _request()
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "rejected_source"
    assert j["research_inference_performed"] is False
    assert j["confirmed_fault"] is False
    assert j["safe_to_work"] is False
    assert j["original_rar_md5_verified_in_this_request"] is False
    assert "SECRET_PRIVATE_PATH" not in str(j)
    assert "traceback" not in str(j).lower()


def test_no_seven_zip_fails_closed_without_claiming_source_provenance(monkeypatch):
    monkeypatch.setattr(original, "MIN_ORIGINAL_RAR_BYTES", 12)
    monkeypatch.setattr(original.shutil, "which", lambda _name: None)
    result = _request()
    # On Windows 7z.exe may still be at Program Files; skip platform-specific
    # fallback assertion if system installation is available in that location.
    assert result.status_code == 200
    assert result.json()["status"] in ("unavailable", "rejected_source")
    assert result.json()["research_inference_performed"] is False


def test_archive_request_does_not_activate_legacy_si_csv_product_ml():
    with TestClient(app) as client:
        r = client.get("/api/integration/capabilities").json()
    assert r["ml"]["inference_enabled"] is False
    from faultmate.integration.ml import load_validated_model
    assert load_validated_model() is None


def test_development_damaged_bearing_miss_is_not_suppressed(monkeypatch):
    """SYNTHETIC score only; test warning flag, never scientific performance."""
    import scripts.run_experimental_paderborn_ml as runner
    monkeypatch.setattr(original.shutil, "which", lambda _: "/synthetic/7z")
    monkeypatch.setattr(runner, "run_archive", lambda *_args, **_kwargs: {
        "research_input_source": {
            "source_records": 80, "unique_signal_pairs": 80,
            "duplicates_excluded": 0,
        },
        "frozen_model_sha256": "f" * 64,
        "experimental_predicted_label": "healthy",
        "experimental_damage_model_score": 0.25,
    })
    result = original._research_score(Path("/synthetic/KA04.rar"), "KA04")
    assert result["source_known_research_truth_label"] == "damaged"
    assert result["historical_known_damaged_false_negative"] is True
    assert result["safe_to_work"] is False
    assert result["model_approved_for_runtime"] is False
    assert "놓친 미탐" in result["message"]


def test_development_healthy_bearing_is_not_falsely_reported_as_damaged_miss(monkeypatch):
    """SYNTHETIC score only; source truth stays separate from prediction."""
    import scripts.run_experimental_paderborn_ml as runner
    monkeypatch.setattr(original.shutil, "which", lambda _: "/synthetic/7z")
    monkeypatch.setattr(runner, "run_archive", lambda *_args, **_kwargs: {
        "research_input_source": {
            "source_records": 80, "unique_signal_pairs": 80,
            "duplicates_excluded": 0,
        },
        "frozen_model_sha256": "f" * 64,
        "experimental_predicted_label": "healthy",
        "experimental_damage_model_score": 0.25,
    })
    result = original._research_score(Path("/synthetic/K001.rar"), "K001")
    assert result["source_known_research_truth_label"] == "healthy"
    assert result["historical_known_damaged_false_negative"] is False
    assert result["safe_to_work"] is False
