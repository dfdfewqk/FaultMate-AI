"""Inspect *only* the official author's tiny public ReadMe file, never sensor data.

Uses gdown --json metadata listing to locate exactly:
  ReadMe-Google Drive.txt
Then downloads only that file into an auto-deleted temporary directory.
The original large BJTU *.z01/*.z02/*.zip sensor archives are NEVER fetched.
No keys, auth, cookies, raw CSV or paid API. Output is a small verification
summary; it never implies raw measurements were audited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

# Direct "python scripts/..." execution otherwise omits repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_bjtu_primary_layout import (
    DRIVE_FOLDER, PublishedSourceError, verify_published_layout,
    PUBLISHED_LAYOUT,
)

EXPECTED_PARTS = frozenset({
    "Data/BJTU_RAO_Bogie_Datasets.z01",
    "Data/BJTU_RAO_Bogie_Datasets.z02",
    "Data/BJTU_RAO_Bogie_Datasets.zip",
})
PUBLIC_README = "ReadMe-Google Drive.txt"
MAX_BYTES = 64 * 1024


def _safe_public_drive_url(link: str) -> bool:
    if not isinstance(link, str) or len(link) > 400 or "\\" in link:
        return False
    try:
        url = urlsplit(link)
        if (url.scheme != "https" or url.hostname != "drive.google.com"
            or url.username is not None or url.password is not None
            or url.fragment):
            return False
        return (
            url.path in ("/uc", "/open")
            and set(k.split("=", 1)[0] for k in url.query.split("&"))
                <= {"id", "export", "confirm"}
            and re.search(r"(?:^|&)id=[A-Za-z0-9_-]{10,}(?:&|$)",
                          url.query) is not None
        ) or bool(re.fullmatch(r"/file/d/[A-Za-z0-9_-]{10,}/view", url.path))
    except ValueError:
        return False


def _summary(text: str, data: bytes, paths: list[str]) -> dict:
    # Review only a small text file. Do not publish secrets/passwords or full
    # copyrighted README paragraphs in CI logs.
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    tokens = text.lower()
    preview = []
    for line in lines[:16]:
        if any(t in line.lower() for t in ("password", "pwd=", "密码", "提取码", "passcode")):
            preview.append("[password_or_access_hint_redacted]")
        else:
            preview.append(line[:120])
    return {
        "status": "original_author_public_readme_fetched_only_not_sensor_dataset",
        "readme_retrieved": True,
        "readme_bytes": len(data),
        "readme_sha256": hashlib.sha256(data).hexdigest(),
        "readme_first_lines_sanitized": preview[:12],
        "published_split_archive_metadata_names_found":
            sorted(EXPECTED_PARTS.intersection(paths)),
        "split_parts_all_listed": EXPECTED_PARTS.issubset(paths),
        "readme_references_zip_or_extract":
            any(x in tokens for x in ("zip", "extract", "unzip", "解压", "压缩")),
        "readme_references_license":
            any(x in tokens for x in ("license", "cc by", "许可", "授权", "copyright")),
        "no_raw_signal_csv_downloaded": True,
        "source_normal_physical_bearings_independently_verified": 0,
        "industrial_runtime_model_approved": False,
        "commercial_reuse_permission_verified": False,
    }


def inspect_author_public_readme(*, timeout: int = 60) -> dict:
    metadata = subprocess.run(
        [sys.executable, "-m", "gdown", DRIVE_FOLDER, "--folder", "--json",
         "--no-cookies"],
        capture_output=True, text=True, check=False, timeout=timeout)
    if metadata.returncode or len(metadata.stdout) > 2_000_000:
        raise PublishedSourceError("official_public_folder_metadata_unavailable")
    all_files = json.loads(metadata.stdout)
    if not isinstance(all_files, list):
        raise PublishedSourceError("official_public_folder_metadata_invalid")
    by_name = {}
    for item in all_files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise PublishedSourceError("bad_public_directory_entry")
        by_name.setdefault(item["path"], []).append(item)
    if len(by_name.get(PUBLIC_README, [])) != 1:
        raise PublishedSourceError("official_readme_not_uniquely_listed")
    url = by_name[PUBLIC_README][0].get("url")
    if not _safe_public_drive_url(url):
        raise PublishedSourceError("readme_download_not_verified_drive_url")
    with TemporaryDirectory(prefix="faultmate-bjtu-public-author-readme-") as td:
        output = Path(td) / PUBLIC_README
        result = subprocess.run(
            [sys.executable, "-m", "gdown", url, "--no-cookies",
             "--quiet", "-O", str(output)],
            capture_output=True, text=True, check=False, timeout=timeout)
        if result.returncode or not output.is_file():
            raise PublishedSourceError("readme_public_file_download_not_available")
        if output.stat().st_size > MAX_BYTES:
            raise PublishedSourceError("readme_unexpected_large_file")
        data = output.read_bytes()
        if b"\x00" in data:
            raise PublishedSourceError("readme_not_plain_text")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("gb18030")
        return _summary(text, data, list(by_name))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = {
        "status": "original_public_readme_not_yet_verified",
        "readme_retrieved": False,
        "no_raw_signal_csv_downloaded": True,
        "source_normal_physical_bearings_independently_verified": 0,
        "industrial_runtime_model_approved": False,
        "commercial_reuse_permission_verified": False,
    }
    try:
        verify_published_layout(json.loads(
            PUBLISHED_LAYOUT.read_text(encoding="utf-8")))
        try:
            result = inspect_author_public_readme()
        except (OSError, ValueError, KeyError, UnicodeError,
                subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            result["probe_error_class"] = (
                str(exc) if isinstance(exc, PublishedSourceError)
                else "public_metadata_or_readme_unavailable"
            )
        if args.out.exists() or args.out.is_symlink():
            raise PublishedSourceError("refuse_overwrite_source_evidence")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(json.dumps({
            "readme_retrieved": result["readme_retrieved"],
            "zip_parts_listed": result.get("split_parts_all_listed"),
            "error_class": result.get("probe_error_class"),
            "no_sensor_data_downloaded": True,
            "healthy_bearings_validated": 0,
        }))
        # Network unavailability is legitimate evidence, not a code failure.
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("BJTU_PUBLIC_README_CHECK_FAILED:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
