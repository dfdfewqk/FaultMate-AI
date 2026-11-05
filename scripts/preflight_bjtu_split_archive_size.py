"""Resource-safe BJTU original split ZIP feasibility (NO archive download).

Inspect exact original-author public filenames from the parent Google Drive
metadata only. Optionally query each exact public file's *HTTP headers*:
one HEAD and, when HEAD does not identify an actual attachment, at most ONE
GET Range bytes=0-0 request. The body is never consumed or saved.

Unlike listing a 30+ GB drive archive, this cannot download any raw CSV
content. A missing/HTML/redirected response reports UNKNOWN, not zero bytes.
The peer-reviewed physical-bearing count remains unknown; no model loads.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_bjtu_primary_layout import (
    DRIVE_FOLDER, PUBLISHED_LAYOUT, PublishedSourceError,
    verify_published_layout,
)
from scripts.probe_bjtu_author_readme import (
    EXPECTED_PARTS, _safe_public_drive_url,
)

ROOT = Path(__file__).resolve().parents[1]
PART_NAMES = frozenset(EXPECTED_PARTS)
REQUEST_LIMIT_BYTES = 1
THIRD_PARTY_ESTIMATED_TOTAL_BYTES = 30_400_000_000
RESOURCE_BUDGET_BYTES = 6_000_000_000


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _read_file_index(*, timeout_seconds: int = 50) -> dict[str, str]:
    command = [
        sys.executable, "-m", "gdown", DRIVE_FOLDER, "--folder",
        "--json", "--no-cookies",
    ]
    returned = subprocess.run(
        command, capture_output=True, text=True, check=False,
        timeout=timeout_seconds,
    )
    if returned.returncode or len(returned.stdout) > 2_000_000:
        raise PublishedSourceError("public_author_folder_listing_unavailable")
    entries = json.loads(returned.stdout)
    if not isinstance(entries, list):
        raise PublishedSourceError("public_author_folder_listing_unexpected")
    found: dict[str, str] = {}
    for item in entries:
        if not isinstance(item, dict):
            raise PublishedSourceError("unexpected_public_listing_entry")
        path, url = item.get("path"), item.get("url")
        if path not in PART_NAMES:
            continue
        if path in found:
            raise PublishedSourceError("duplicate_official_archive_part_name")
        if not _safe_public_drive_url(url):
            raise PublishedSourceError("untrusted_archive_part_metadata_link")
        found[path] = url
    return found


def _attachment_size_from_headers(headers, status: int) -> int | None:
    """Only trust a 206 Content-Range, never a Drive HTML preview length."""
    if status != 206:
        return None
    content_type = str(headers.get("Content-Type", "")).lower()
    if "html" in content_type or "json" in content_type:
        return None
    content_range = str(headers.get("Content-Range", ""))
    m = re.fullmatch(r"bytes 0-0/([1-9]\d*)", content_range)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _single_part_head_or_one_byte_range(url: str, *, timeout_seconds: int = 12) -> dict:
    """Never read response.body, even for 200, 302 or 206. No cookies."""
    if not _safe_public_drive_url(url):
        raise PublishedSourceError("untrusted_public_source_url")
    opener = build_opener(_NoRedirects)
    results = []
    reported_size = None
    for method in ("HEAD", "GET"):
        hdr = {"User-Agent": "FaultMate-AI/Source-Metadata-Only"}
        if method == "GET":
            hdr["Range"] = f"bytes=0-{REQUEST_LIMIT_BYTES - 1}"
        req = Request(url, headers=hdr, method=method)
        try:
            # Never .read(), not even one byte. Closing response immediately
            # prevents an accidental 30-GB download from large-file endpoints.
            with opener.open(req, timeout=timeout_seconds) as resp:
                status = resp.status
                observed = _attachment_size_from_headers(resp.headers, status)
                if observed is not None:
                    reported_size = observed
                ct = str(resp.headers.get("Content-Type", "")).lower()
                results.append({
                    "method": method,
                    "http_status": status,
                    "content_type_class": (
                        "html_or_json" if "html" in ct or "json" in ct else "other"
                    ),
                    "trusted_total_archive_bytes": observed,
                })
        except HTTPError as exc:
            # HTTP 30x is not followed; signed redirect URL is never logged.
            results.append({
                "method": method, "http_status": int(exc.code),
                "content_type_class": "unresolved",
                "trusted_total_archive_bytes": None,
            })
            exc.close()
        except (OSError, URLError, ValueError):
            results.append({
                "method": method, "http_status": None,
                "content_type_class": "unavailable",
                "trusted_total_archive_bytes": None,
            })
        if reported_size is not None:
            break
    return {
        "trusted_length_bytes": reported_size,
        "request_headers_only": True,
        "downloaded_bytes": 0,
        "http_attempts": results,
    }


def inspect_original_source_feasibility(*, online: bool = False,
                                         disk_path: Path | None = None) -> dict:
    verify_published_layout(json.loads(
        PUBLISHED_LAYOUT.read_text(encoding="utf-8")))
    disk = shutil.disk_usage(disk_path or ROOT)
    result = {
        "status": "source_metadata_only_unverified_raw_archive",
        "author_archive_part_count_expected": 3,
        "author_archive_part_names": sorted(PART_NAMES),
        "split_archive_parts_listed": None,
        "source_listing_attempted": online,
        "part_reports": [],
        "third_party_download_size_estimate_bytes": THIRD_PARTY_ESTIMATED_TOTAL_BYTES,
        "third_party_estimate_original_archive_checksum_verified": False,
        "actual_total_source_archive_bytes_verified": None,
        "current_environment_free_disk_bytes": int(disk.free),
        "automatic_ci_transfer_budget_bytes": RESOURCE_BUDGET_BYTES,
        "safe_to_auto_download_or_extract_large_archive": False,
        "original_csv_or_split_zip_data_downloaded": False,
        "no_paid_api_calls": True,
        "new_physically_independent_normal_bearings_verified": 0,
        "new_normal_specificity_measured": False,
        "production_bearing_model_approved": False,
        "blockers": [
            "original_split_archive_bytes_and_checksum_unverified",
            "full_archive_exceeds_declared_auto_transfer_budget_if_estimate_correct",
            "normal_physical_bearing_identifiers_not_available_from_filename_only",
            "BJTU_nine_conditions_do_not_match_frozen_Paderborn_four_conditions",
            "dataset_commercial_use_and_redistribution_terms_not_verified",
        ],
    }
    if not online:
        return result
    try:
        items = _read_file_index()
        result["split_archive_parts_listed"] = PART_NAMES == set(items)
        result["public_index_file_names_identified"] = sorted(items)
        for name in sorted(PART_NAMES):
            report = {"part_name": name, "present_in_public_listing": name in items}
            if name in items:
                report.update(_single_part_head_or_one_byte_range(items[name]))
            else:
                report.update({"trusted_length_bytes": None,
                               "downloaded_bytes": 0, "http_attempts": []})
            result["part_reports"].append(report)
        sizes = [x["trusted_length_bytes"] for x in result["part_reports"]]
        if all(type(x) is int and x > 0 for x in sizes):
            result["actual_total_source_archive_bytes_verified"] = sum(sizes)
            if sum(sizes) > disk.free:
                result["blockers"].append("entire_original_archives_exceed_free_runner_disk")
            if sum(sizes) > RESOURCE_BUDGET_BYTES:
                result["blockers"].append("verified_original_archives_exceed_automatic_budget")
        else:
            result["blockers"].append("http_headers_cannot_verify_all_three_part_sizes")
    except (OSError, ValueError, subprocess.TimeoutExpired,
            json.JSONDecodeError) as exc:
        result["online_error_class"] = (
            str(exc) if isinstance(exc, PublishedSourceError)
            else "public_file_metadata_unavailable"
        )
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online-head-only", action="store_true",
                        help="GDrive public file metadata; never fetch any body")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect_original_source_feasibility(online=args.online_head_only)
        if args.out.exists() or args.out.is_symlink():
            raise PublishedSourceError("refuse_overwrite_split_archive_evidence")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as target:
            json.dump(result, target, ensure_ascii=False, indent=2)
            target.write("\n")
        print(json.dumps({
            "parts_listed": result["split_archive_parts_listed"],
            "confirmed_total_size_bytes": result["actual_total_source_archive_bytes_verified"],
            "auto_large_download_blocked": not result["safe_to_auto_download_or_extract_large_archive"],
            "sensor_bytes_downloaded": False,
            "physical_normal_bearings_verified": 0,
        }))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("BJTU_ARCHIVE_SIZE_PREFLIGHT_FAIL_CLOSED:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
