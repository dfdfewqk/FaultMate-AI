"""No original BJTU sensor bytes permitted in split-archive budget preflight."""
from __future__ import annotations

from email.message import Message
import json
from pathlib import Path
import subprocess
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from scripts import preflight_bjtu_split_archive_size as p


def test_offline_preflight_never_requests_or_loads_original_model(monkeypatch):
    monkeypatch.setattr(p, "_read_file_index",
                        lambda: pytest.fail("offline preflight called Google Drive"))
    r = p.inspect_original_source_feasibility(online=False)
    assert r["source_listing_attempted"] is False
    assert r["third_party_download_size_estimate_bytes"] == 30_400_000_000
    assert r["third_party_estimate_original_archive_checksum_verified"] is False
    assert r["safe_to_auto_download_or_extract_large_archive"] is False
    assert r["original_csv_or_split_zip_data_downloaded"] is False
    assert r["new_physically_independent_normal_bearings_verified"] == 0
    assert r["new_normal_specificity_measured"] is False
    assert r["production_bearing_model_approved"] is False
    assert r["no_paid_api_calls"] is True
    assert len(r["author_archive_part_names"]) == 3


def test_google_html_content_length_cannot_be_used_as_original_archive_size():
    for status, ctype, crange in [
        (200, "text/html", None),
        (200, "application/octet-stream", None),
        (206, "text/html", "bytes 0-0/30400000000"),
        (206, "application/octet-stream", "bytes 1-1/30400000000"),
    ]:
        h = Message()
        h["Content-Type"] = ctype
        if crange:
            h["Content-Range"] = crange
        h["Content-Length"] = "30400000000"
        assert p._attachment_size_from_headers(h, status) is None


def test_exact_partial_content_range_may_indicate_original_length_only():
    h = Message()
    h["Content-Type"] = "application/zip"
    h["Content-Range"] = "bytes 0-0/12500000000"
    assert p._attachment_size_from_headers(h, 206) == 12_500_000_000
    assert p._attachment_size_from_headers(h, 200) is None


def test_http_head_and_range_never_read_large_body_or_follow_redirect(monkeypatch):
    called = []

    class FakeReply:
        status = 206
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            pass

        def read(self, *_a):
            pytest.fail("reading entire archive body was forbidden")

    FakeReply.headers["Content-Type"] = "application/octet-stream"
    FakeReply.headers["Content-Range"] = "bytes 0-0/30400000000"

    class FakeOpener:
        def open(self, request, timeout):
            called.append((request.get_method(), request.get_header("Range"), timeout))
            if request.get_method() == "HEAD":
                return FakeReply()
            return FakeReply()

    monkeypatch.setattr(p, "build_opener", lambda *_: FakeOpener())
    r = p._single_part_head_or_one_byte_range(
        "https://drive.google.com/uc?id=ABCDEFGHIJKLMNO"
    )
    assert r["trusted_length_bytes"] == 30_400_000_000
    assert r["downloaded_bytes"] == 0
    assert called == [("HEAD", None, 12)]


def test_gdrive_redirect_not_followed_and_html_does_not_prove_archive(monkeypatch):
    seen = []

    class HtmlReply:
        status = 200
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self, *_args):
            pytest.fail("HTML page body should not be read")

    HtmlReply.headers["Content-Type"] = "text/html"
    HtmlReply.headers["Content-Length"] = "900"

    class FakeOpener:
        def open(self, request, timeout):
            seen.append(request.get_method())
            if request.get_method() == "HEAD":
                raise HTTPError(request.full_url, 302, "redirect",
                                Message(), None)
            return HtmlReply()

    monkeypatch.setattr(p, "build_opener", lambda *_: FakeOpener())
    r = p._single_part_head_or_one_byte_range(
        "https://drive.google.com/uc?id=ABCDEFGHIJKLMNO"
    )
    assert [x["http_status"] for x in r["http_attempts"]] == [302, 200]
    assert r["trusted_length_bytes"] is None
    assert r["downloaded_bytes"] == 0
    assert seen == ["HEAD", "GET"]


def test_official_three_names_exact_only_and_missing_parts_rejected(monkeypatch):
    link = "https://drive.google.com/uc?id=ABCDEFGHIJKLMNO"
    docs = [
        {"path": name, "url": link} for name in sorted(p.PART_NAMES)
    ] + [{"path": "ReadMe-Google Drive.txt", "url": link}]
    monkeypatch.setattr(p.subprocess, "run", lambda cmd, **_k:
                        subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(docs)))
    assert p._read_file_index() == {n: link for n in p.PART_NAMES}
    docs[0]["url"] = "https://untrusted.invalid/uc?id=ABCDEFGHIJKLMNO"
    with pytest.raises(p.PublishedSourceError, match="untrusted_archive"):
        p._read_file_index()


def test_three_verified_sizes_still_cannot_auto_download(monkeypatch):
    link = "https://drive.google.com/uc?id=ABCDEFGHIJKLMNO"
    monkeypatch.setattr(p, "_read_file_index", lambda: {n: link for n in p.PART_NAMES})
    monkeypatch.setattr(p, "_single_part_head_or_one_byte_range",
                        lambda *_args, **_kw:
                        {"trusted_length_bytes": 11_000_000_000,
                         "downloaded_bytes": 0, "http_attempts": []})
    r = p.inspect_original_source_feasibility(online=True)
    assert r["split_archive_parts_listed"] is True
    assert r["actual_total_source_archive_bytes_verified"] == 33_000_000_000
    assert "verified_original_archives_exceed_automatic_budget" in r["blockers"]
    assert r["safe_to_auto_download_or_extract_large_archive"] is False
    assert r["new_physically_independent_normal_bearings_verified"] == 0


def test_part_metadata_or_size_unknown_is_not_reported_as_zero(monkeypatch):
    link = "https://drive.google.com/uc?id=ABCDEFGHIJKLMNO"
    monkeypatch.setattr(p, "_read_file_index", lambda: {n: link for n in p.PART_NAMES})
    monkeypatch.setattr(p, "_single_part_head_or_one_byte_range",
                        lambda *_args, **_kw:
                        {"trusted_length_bytes": None, "downloaded_bytes": 0,
                         "http_attempts": []})
    r = p.inspect_original_source_feasibility(online=True)
    assert r["actual_total_source_archive_bytes_verified"] is None
    assert "http_headers_cannot_verify_all_three_part_sizes" in r["blockers"]
    assert r["safe_to_auto_download_or_extract_large_archive"] is False


def test_missing_official_archive_part_cannot_prove_archive_complete(monkeypatch):
    link = "https://drive.google.com/uc?id=ABCDEFGHIJKLMNO"
    one = next(iter(p.PART_NAMES))
    monkeypatch.setattr(p, "_read_file_index", lambda: {one: link})
    monkeypatch.setattr(p, "_single_part_head_or_one_byte_range",
                        lambda *_args, **_kw:
                        {"trusted_length_bytes": None,
                         "downloaded_bytes": 0, "http_attempts": []})
    r = p.inspect_original_source_feasibility(online=True)
    assert r["split_archive_parts_listed"] is False
    assert sum(x["present_in_public_listing"] for x in r["part_reports"]) == 1
    assert r["actual_total_source_archive_bytes_verified"] is None


def test_cli_never_overwrites_existing_evidence(tmp_path):
    output = tmp_path / "report.json"
    assert p.main(["--out", str(output)]) == 0
    d = json.loads(output.read_text(encoding="utf-8"))
    assert d["original_csv_or_split_zip_data_downloaded"] is False
    assert d["safe_to_auto_download_or_extract_large_archive"] is False
    preserved = output.read_bytes()
    assert p.main(["--out", str(output)]) == 2
    assert output.read_bytes() == preserved
