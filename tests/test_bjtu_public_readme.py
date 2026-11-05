"""Public original-author readme probe must never download source sensor archives."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from scripts import probe_bjtu_author_readme as probe


@pytest.mark.parametrize("url", [
    "http://drive.google.com/uc?id=ABCDEFGHIJKLMNO",
    "https://drive.google.com.evil.invalid/uc?id=ABCDEFGHIJKLMNO",
    "https://other.example/uc?id=ABCDEFGHIJKLMNO",
    "https://user@drive.google.com/uc?id=ABCDEFGHIJKLMNO",
    "https://drive.google.com/uc?id=bad",
    "https://drive.google.com/uc?id=ABCDEFGHIJKLMNO&redirect=https://evil",
    "https://drive.google.com/uc?id=ABCDEFGHIJKLMNO#secret",
])
def test_readme_provider_location_rejects_fake_domain_credentials_redirect(url):
    assert probe._safe_public_drive_url(url) is False


def test_gdown_readme_success_is_only_doc_metadata_not_sensor_validation(monkeypatch):
    file_id = "A" * 23
    url = f"https://drive.google.com/uc?id={file_id}"
    items = [{"url": url, "path": "ReadMe-Google Drive.txt"}]
    for item in sorted(probe.EXPECTED_PARTS):
        items.append({"url": url, "path": item})
    calls = []

    def mock_run(cmd, **kwargs):
        calls.append(cmd)
        if "--json" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(items), stderr="")
        assert cmd[3] == url
        assert "-O" in cmd
        assert "--no-cookies" in cmd
        target = Path(cmd[-1])
        target.write_text(
            "The BJTU dataset has three split zip files.\n"
            "Extract after downloading all segments.\n"
            "Password: sensitive value do not show\n",
            encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(probe.subprocess, "run", mock_run)
    result = probe.inspect_author_public_readme()
    assert result["readme_retrieved"] is True
    assert result["split_parts_all_listed"] is True
    assert result["readme_references_zip_or_extract"] is True
    assert result["readme_references_license"] is False
    assert len(result["published_split_archive_metadata_names_found"]) == 3
    assert result["no_raw_signal_csv_downloaded"] is True
    assert result["source_normal_physical_bearings_independently_verified"] == 0
    assert result["industrial_runtime_model_approved"] is False
    assert any("[password_or_access_hint_redacted]" in x
               for x in result["readme_first_lines_sanitized"])
    assert "sensitive value" not in str(result)
    assert len(calls) == 2
    assert all("BJTU_RAO_Bogie_Datasets.zip" not in str(cmd)
               for cmd in calls)


def test_absent_public_readme_is_not_fabricated(monkeypatch):
    data = json.dumps([{
        "path": "Data/BJTU_RAO_Bogie_Datasets.zip",
        "url": "https://drive.google.com/uc?id=" + "A" * 23,
    }])
    monkeypatch.setattr(probe.subprocess, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess(args[0], 0, stdout=data))
    with pytest.raises(probe.PublishedSourceError, match="not_uniquely_listed"):
        probe.inspect_author_public_readme()


def test_no_other_host_is_ever_used_for_download(monkeypatch):
    data = json.dumps([{
        "path": "ReadMe-Google Drive.txt",
        "url": "https://attacker.example/uc?id=" + "A" * 23,
    }])
    monkeypatch.setattr(probe.subprocess, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess(args[0], 0, stdout=data))
    with pytest.raises(probe.PublishedSourceError, match="not_verified_drive_url"):
        probe.inspect_author_public_readme()


def test_source_access_failure_yields_honest_report_no_overwrite(monkeypatch,
                                                                 tmp_path):
    def deny():
        raise probe.PublishedSourceError("official_readme_not_uniquely_listed")

    monkeypatch.setattr(probe, "inspect_author_public_readme", deny)
    out = tmp_path / "review" / "readme-summary.json"
    assert probe.main(["--out", str(out)]) == 0
    j = json.loads(out.read_text(encoding="utf-8"))
    assert j["readme_retrieved"] is False
    assert j["source_normal_physical_bearings_independently_verified"] == 0
    assert j["probe_error_class"] == "official_readme_not_uniquely_listed"
    content = out.read_bytes()
    assert probe.main(["--out", str(out)]) == 2
    assert out.read_bytes() == content
