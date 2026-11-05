"""Local split-ZIP metadata listing: never extract or imply independent bearings."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from scripts import audit_bjtu_local_split_zip_intake as m


def _dummy_parts(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for part in m.PARTS:
        (folder / part).write_bytes(b"NOT A REAL DATASET")


def _sample_7z_listing() -> bytes:
    names = [f"BJTU_RAO_Bogie_Datasets/M0_G0_LA0_RA0/"
             f"Sample_{i}/data_{sensor}_M0_G0_LA0_RA0_20Hz_0kN.csv"
             for i in range(1, 10)
             for sensor in ("motor", "gearbox", "leftaxlebox", "rightaxlebox")]
    return ("\n".join(f"Path = {name}\nSize = 32" for name in names)
            + "\n").encode("utf-8")


def test_missing_archive_directory_does_not_call_7zip_or_download(monkeypatch):
    monkeypatch.setattr(m.subprocess, "run",
                        lambda *_args, **_kw: pytest.fail("must not inspect absent data"))
    report = m.inspect_existing_archives_only(None)
    assert report["status"] == "local_original_split_archives_not_supplied"
    assert report["all_three_locally_present"] is False
    assert report["archive_listing_attempted"] is False
    assert report["distinct_normal_physical_bearings_verified"] == 0
    assert report["original_signal_bytes_read"] is False
    assert report["archived_csv_samples_extracted"] is False
    assert report["production_model_approved"] is False


def test_missing_one_original_part_prevents_any_listing(tmp_path, monkeypatch):
    _dummy_parts(tmp_path)
    (tmp_path / m.PARTS[1]).unlink()
    monkeypatch.setattr(m.subprocess, "run",
                        lambda *_args, **_kw: pytest.fail("incomplete ZIP must not be listed"))
    r = m.inspect_existing_archives_only(tmp_path, sevenzip="7z")
    assert r["status"] == "original_three_split_archives_incomplete"
    assert r["all_three_locally_present"] is False
    assert r["observed_csv_count"] is None


def test_fake_metadata_list_only_still_does_not_verify_raw_or_bearing_ids(
    tmp_path, monkeypatch
):
    _dummy_parts(tmp_path)
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        assert cmd == ["7z", "l", "-slt", "-ba",
                       str(tmp_path / "BJTU_RAO_Bogie_Datasets.zip")]
        assert kwargs["timeout"] <= 160
        assert kwargs["capture_output"] is True
        return subprocess.CompletedProcess(cmd, 0, stdout=_sample_7z_listing(), stderr=b"")

    monkeypatch.setattr(m.subprocess, "run", run)
    r = m.inspect_existing_archives_only(tmp_path, sevenzip="7z")
    assert calls and len(calls) == 1
    assert r["archive_listing_attempted"] is True
    assert r["archive_file_listing_returncode_success"] is True
    assert r["observed_csv_count"] == 36
    assert r["observed_normal_label_csv_count"] == 36
    assert r["original_file_layout_matches_author_expected_count"] is False
    assert r["distinct_normal_physical_bearings_verified"] == 0
    assert r["original_archive_crc_or_sha_verified"] is False
    assert r["archived_csv_samples_extracted"] is False
    assert r["production_model_approved"] is False


@pytest.mark.parametrize("bad_member", [
    "../secret.txt",
    "/absolute/path.csv",
    "C:\\Users\\secret.csv",
    "BJTU_RAO_Bogie_Datasets/../exfiltrate.csv",
    "BJTU_RAO_Bogie_Datasets//weird.csv",
])
def test_archive_path_traversal_and_unsafe_names_rejected(bad_member):
    listing = f"Path = {bad_member}\nSize = 1\n"
    with pytest.raises(m.PublishedSourceError, match="malicious_archive_member"):
        m._parse_7zip_listing(listing)


def test_archive_list_duplicate_fails_closed():
    s = ("Path = BJTU_RAO_Bogie_Datasets/sample.csv\n"
         "Path = BJTU_RAO_Bogie_Datasets/sample.csv\n")
    with pytest.raises(m.PublishedSourceError, match="duplicate_original_archive"):
        m._parse_7zip_listing(s)


def test_large_archive_list_output_fails_closed():
    with pytest.raises(m.PublishedSourceError, match="too_large"):
        m._parse_7zip_listing("x" * (m.MAX_LISTING_BYTES + 1))


def test_archive_listing_fail_does_not_fake_normal_file_count(tmp_path, monkeypatch):
    _dummy_parts(tmp_path)
    monkeypatch.setattr(m.subprocess, "run",
                        lambda cmd, **kwargs:
                        subprocess.CompletedProcess(cmd, 2, stdout=b"", stderr=b""))
    r = m.inspect_existing_archives_only(tmp_path, sevenzip="7z")
    assert r["status"] == "split_archive_listing_failed"
    assert r["archive_file_listing_returncode_success"] is False
    assert r["observed_normal_label_csv_count"] is None
    assert r["distinct_normal_physical_bearings_verified"] == 0


def test_cli_offline_missing_files_report_never_overwrites_existing(tmp_path):
    f = tmp_path / "status.json"
    assert m.main(["--out", str(f)]) == 0
    j = json.loads(f.read_text(encoding="utf-8"))
    assert j["all_three_locally_present"] is False
    assert j["file_name_inventory_is_physical_bearing_inventory"] is False
    old = f.read_bytes()
    assert m.main(["--out", str(f)]) == 2
    assert f.read_bytes() == old
