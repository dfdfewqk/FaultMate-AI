"""Only synthetic MAT data; the real first-party source is exercised by CI."""
import hashlib
import io

import numpy as np
from scipy.io import savemat
import pytest

from scripts import verify_hust_official_public_original as source


def synthetic_mat():
    buffer = io.BytesIO()
    savemat(buffer, {"data": np.arange(500001, dtype=np.float64)})
    return buffer.getvalue()


def fake_entry(raw):
    return {
        "name": "N400.mat", "folder": "HUST bearing dataset",
        "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "download_url": "https://data.mendeley.com/public-files/fake-test",
    }


def test_one_synthetic_original_sha_and_shape_are_checked_but_no_model_approved(monkeypatch):
    raw = synthetic_mat()
    monkeypatch.setattr(source, "CROSS_CHECK_SHA256", hashlib.sha256(raw).hexdigest())
    result = source.verify_one_official_original(
        [fake_entry(raw)], downloader=lambda _, __: raw)
    assert result["original_bytes_verified_to_first_party_sha256"] is True
    assert result["mat_numeric_sample_count"] == 500001
    assert result["si_sensor_calibration_verified"] is False
    assert result["new_independent_specificity_measured"] is False
    assert result["paderborn_vibration_current_model_compatible"] is False
    assert result["production_model_activation_allowed"] is False
    assert result["paid_ai_api_called"] is False


def test_sha_source_mismatch_never_downloads(monkeypatch):
    raw = synthetic_mat()
    entry = fake_entry(raw)
    calls = []
    def downloader(*args):
        calls.append(args)
        return raw
    with pytest.raises(source.PublicSourceError, match="publisher_sha_differs"):
        source.verify_one_official_original([entry], downloader=downloader)
    assert not calls


def test_changed_raw_original_rejected_after_download(monkeypatch):
    raw = synthetic_mat()
    monkeypatch.setattr(source, "CROSS_CHECK_SHA256", hashlib.sha256(raw).hexdigest())
    altered = raw[:-1] + bytes([raw[-1] ^ 1])
    with pytest.raises(source.PublicSourceError, match="actual_original_sha256_mismatch"):
        source.verify_one_official_original([fake_entry(raw)], downloader=lambda *_: altered)


def test_duplicate_original_name_not_accepted():
    raw = b"test"
    with pytest.raises(source.PublicSourceError, match="not_uniquely_listed"):
        source.verify_one_official_original([fake_entry(raw),fake_entry(raw)])


def test_source_auth_api_url_must_match_fixed_publisher_and_version():
    for url in ("http://data.mendeley.com/public-api/datasets/cbv7jyx4p9/files",
                "https://phishing.example/public-api/datasets/cbv7jyx4p9/files",
                "https://data.mendeley.com/api/datasets/cbv7jyx4p9/files"):
        with pytest.raises(source.PublicSourceError, match="publisher_api_origin_not_trusted"):
            source._publisher_json(url)


def test_trusted_index_names_and_size(monkeypatch):
    digest = hashlib.sha256(b"not-a-real-file").hexdigest()
    folders = [{"id":"folder-1","name":"HUST bearing dataset"}]
    example = {"filename":"N400.mat","content_details":{
        "size":12345, "sha256_hash":digest,
        "download_url":"https://data.mendeley.com/public-files/original"}}
    def mock_json(url):
        if "/folders/" in url:
            return folders
        if "folder_id=folder-1" in url:
            return [example]
        return []
    monkeypatch.setattr(source,"_publisher_json", mock_json)
    index = source.published_files()
    assert len(index) == 1
    assert index[0]["name"] == "N400.mat"
    assert index[0]["sha256"] == digest


def test_unverified_publisher_hash_or_http_disallowed(monkeypatch):
    folders = [{"id":"f-1","name":"HUST bearing dataset"}]
    invalid = {"filename":"N400.mat","content_details":{
        "size":100, "sha256_hash":"nohash",
        "download_url":"http://evil.test/file.mat"}}
    def mock_json(url):
        if "/folders/" in url:
            return folders
        return [invalid]
    monkeypatch.setattr(source, "_publisher_json", mock_json)
    with pytest.raises(source.PublicSourceError, match="sha_or_download_missing"):
        source.published_files()
