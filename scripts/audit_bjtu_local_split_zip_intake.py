"""Read-only local intake for AUTHOR's original BJTU split ZIP if already present.

Works ONLY when three original named segments already exist in a chosen
directory. Calls '7z l -slt -ba' on the final .zip volume, never 7z 'x'/'e',
never downloads any archive and never modifies source files. Produces a
manifest summary, not extracted CSVs or physical-bearing provenance.

File-name/central-directory metadata and 36 nominal healthy CSVs cannot
verify source file SHA/checksums, individual healthy bearing IDs, data license,
or validity of the existing Paderborn frozen classifier for this dataset.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_bjtu_primary_layout import (
    PUBLISHED_LAYOUT, PublishedSourceError, verify_published_layout,
)

PARTS = (
    "BJTU_RAO_Bogie_Datasets.z01",
    "BJTU_RAO_Bogie_Datasets.z02",
    "BJTU_RAO_Bogie_Datasets.zip",
)
ZIP_NAME = PARTS[-1]
MAX_LISTING_BYTES = 12_000_000
MAX_METADATA_PATHS = 20_000


def _initial_report() -> dict:
    return {
        "status": "local_original_split_archives_not_supplied",
        "expected_zip_part_names": list(PARTS),
        "all_three_locally_present": False,
        "source_part_bytes": {},
        "local_split_archives_total_bytes": None,
        "archive_listing_attempted": False,
        "archive_file_listing_returncode_success": False,
        "observed_csv_count": None,
        "observed_normal_label_csv_count": None,
        "original_archive_crc_or_sha_verified": False,
        "original_signal_bytes_read": False,
        "archived_csv_samples_extracted": False,
        "file_name_inventory_is_physical_bearing_inventory": False,
        "distinct_normal_physical_bearings_verified": 0,
        "model_inference_performed": False,
        "commercial_dataset_license_verified": False,
        "production_model_approved": False,
        "blockers": [
            "complete_author_source_parts_not_preverified",
            "original_cryptographic_checksums_not_available_or_unverified",
            "physical_bearing_identities_not_in_filename_metadata",
            "different_bearing_hardware_and_nine_vs_four_operating_conditions",
        ],
    }


def _parse_7zip_listing(output: str) -> list[str]:
    """Extract only file paths; no paths are used for filesystem I/O."""
    if not isinstance(output, str) or len(output.encode("utf-8")) > MAX_LISTING_BYTES:
        raise PublishedSourceError("7zip_list_output_too_large")
    found: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        if not line.startswith("Path = "):
            continue
        path = line[7:].strip().replace("\\", "/")
        if (not path or len(path) > 600 or any(ord(c) < 32 for c in path)
            or path.startswith("/") or
            re.match(r"^[A-Za-z]:", path) or
            any(p in ("", ".", "..") for p in path.split("/"))):
            raise PublishedSourceError("malicious_archive_member_name")
        # 7z -slt may include the archive itself; its name is not a sample.
        if path in PARTS:
            continue
        if path in seen:
            raise PublishedSourceError("duplicate_original_archive_member_name")
        seen.add(path)
        found.append(path)
        if len(found) > MAX_METADATA_PATHS:
            raise PublishedSourceError("excess_original_archive_members")
    return found


def inspect_existing_archives_only(source_dir: Path | None, *, sevenzip: str | None = None) -> dict:
    verify_published_layout(json.loads(PUBLISHED_LAYOUT.read_text(encoding="utf-8")))
    report = _initial_report()
    if source_dir is None:
        return report
    if not source_dir.is_dir() or source_dir.is_symlink():
        report["status"] = "source_dir_unavailable_or_symlink"
        return report
    parts = [source_dir / name for name in PARTS]
    if any(p.is_symlink() or not p.is_file() or p.stat().st_size <= 0
           for p in parts):
        report["status"] = "original_three_split_archives_incomplete"
        return report
    # Size is measured from the existing LOCAL files, not guessed from
    # third-party dataset download estimates.
    report["all_three_locally_present"] = True
    report["source_part_bytes"] = {p.name: p.stat().st_size for p in parts}
    report["local_split_archives_total_bytes"] = sum(report["source_part_bytes"].values())
    tool = sevenzip or shutil.which("7zz") or shutil.which("7z")
    if not tool:
        report["status"] = "split_zip_listing_tool_unavailable"
        return report
    command = [tool, "l", "-slt", "-ba", str(parts[-1])]
    report["archive_listing_attempted"] = True
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=160,
            check=False,
        )
        if completed.returncode:
            report["status"] = "split_archive_listing_failed"
            return report
        if len(completed.stdout) > MAX_LISTING_BYTES:
            report["status"] = "split_archive_listing_exceeds_safe_output"
            return report
        paths = _parse_7zip_listing(completed.stdout.decode(
            "utf-8", errors="replace"))
        if not paths:
            report["status"] = "no_original_archive_file_names"
            return report
        csvs = [p for p in paths if p.lower().endswith(".csv")]
        healthy = [p for p in csvs if "/M0_G0_LA0_RA0/" in "/" + p]
        report["archive_file_listing_returncode_success"] = True
        report["observed_archive_member_count"] = len(paths)
        report["observed_csv_count"] = len(csvs)
        report["observed_normal_label_csv_count"] = len(healthy)
        report["original_file_layout_matches_author_expected_count"] = (
            len(csvs) == 1836 and len(healthy) == 36)
        report["status"] = "split_zip_listing_only_no_original_csv_integrity_or_bearing_proof"
        return report
    except (OSError, ValueError, subprocess.TimeoutExpired,
            UnicodeDecodeError) as exc:
        report["status"] = ("invalid_archive_manifest_path"
                            if isinstance(exc, PublishedSourceError)
                            else "split_zip_listing_unavailable")
        return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing-source-dir", type=Path,
                        help="Only if three matching source ZIP parts already exist locally.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = inspect_existing_archives_only(args.existing_source_dir)
        if args.out.exists() or args.out.is_symlink():
            raise PublishedSourceError("refuse_overwrite_archive_intake_report")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(json.dumps({
            "status": report["status"],
            "three_parts_present": report["all_three_locally_present"],
            "csv_file_count": report["observed_csv_count"],
            "normal_label_csv_file_count": report["observed_normal_label_csv_count"],
            "independent_healthy_physical_bearings_verified": 0,
            "original_data_downloaded": False,
        }))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("BJTU_LOCAL_ARCHIVE_INTAKE_FAIL_CLOSED:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
