"""Verify a Paderborn K001 RAR against public archive metadata and structure.

This command does NOT extract signals, infer physical units, or train models.
The exact K001 MD5 below is published by the Zenodo Paderborn archive
(https://zenodo.org/records/15845309); independently verify the source before
using the archived dataset. The source's CC BY-NC 4.0 license still applies.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

K001_ZENODO_MD5 = "af6dc58283d356cd438e7738a2d525b8"
K001_ZENODO_RECORD = "https://zenodo.org/records/15845309"
K001_MIN_REASONABLE_BYTES = 100_000_000
RECORDING_NAME = re.compile(r"^(N\d{2}_M\d{2}_F\d{2})_K001_(\d+)\.mat$", re.IGNORECASE)


class SourceVerificationError(ValueError):
    """The supplied file has not passed source verification."""


def file_hashes(path: Path) -> tuple[str, str]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            md5.update(block)
            sha256.update(block)
    return md5.hexdigest(), sha256.hexdigest()


def archive_recordings(listing: str) -> dict[str, list[int]]:
    """Require four unique operating conditions, with recordings 1..20 each."""
    recordings: dict[str, list[int]] = defaultdict(list)
    invalid_mat = []
    for line in listing.splitlines():
        if not line.startswith("Path = "):
            continue
        filename = line[len("Path = "):].strip().replace("\\", "/").rsplit("/", 1)[-1]
        if not filename.lower().endswith(".mat"):
            continue
        match = RECORDING_NAME.fullmatch(filename)
        if not match:
            invalid_mat.append(filename)
            continue
        recordings[match.group(1).upper()].append(int(match.group(2)))
    if invalid_mat:
        raise SourceVerificationError(f"unexpected_mat_filenames:{invalid_mat[:5]}")
    if len(recordings) != 4 or sum(map(len, recordings.values())) != 80:
        raise SourceVerificationError(
            f"unexpected_recording_inventory:conditions={len(recordings)};count={sum(map(len, recordings.values()))}"
        )
    for condition, numbers in recordings.items():
        if sorted(numbers) != list(range(1, 21)):
            raise SourceVerificationError(f"missing_or_duplicate_recordings:{condition}")
    return dict(sorted(recordings.items()))


def find_7zip() -> str:
    for program in ("7z", "7zz", "7za"):
        found = shutil.which(program)
        if found:
            return found
    candidate = Path(r"C:\Program Files\7-Zip\7z.exe")
    if candidate.is_file():
        return str(candidate)
    raise SourceVerificationError("sevenzip_not_found")


def inspect_archive(path: Path, *, sevenzip: str | None = None,
                    expected_md5: str = K001_ZENODO_MD5,
                    minimum_bytes: int = K001_MIN_REASONABLE_BYTES) -> dict:
    if not path.is_file():
        raise SourceVerificationError("archive_not_found")
    if path.name.lower() != "k001.rar":
        raise SourceVerificationError("archive_filename_not_k001.rar")
    size = path.stat().st_size
    if size < minimum_bytes:
        raise SourceVerificationError(f"archive_too_small:size={size};minimum={minimum_bytes}")
    actual_md5, actual_sha256 = file_hashes(path)
    if actual_md5.lower() != expected_md5.lower():
        raise SourceVerificationError(f"zenodo_md5_mismatch:observed={actual_md5};expected={expected_md5}")
    executable = sevenzip or find_7zip()
    integrity = subprocess.run(
        [executable, "t", str(path)], capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if integrity.returncode != 0:
        raise SourceVerificationError(f"sevenzip_test_failed:exit={integrity.returncode}")
    listing = subprocess.run(
        [executable, "l", "-slt", "-ba", str(path)], capture_output=True,
        text=True, encoding="utf-8", errors="replace", check=False,
    )
    if listing.returncode != 0:
        raise SourceVerificationError(f"sevenzip_listing_failed:exit={listing.returncode}")
    conditions = archive_recordings(listing.stdout)
    return {
        "status": "archive_matches_zenodo_and_inventory",
        "archive": str(path.resolve()),
        "size_bytes": size,
        "md5": actual_md5,
        "sha256": actual_sha256,
        "reference_md5_source": K001_ZENODO_RECORD,
        "sevenzip_integrity": "passed",
        "conditions": {key: len(value) for key, value in conditions.items()},
        "mat_recordings": 80,
        "bearing_label": "healthy",
        "physical_units_verified": False,
        "csv_generated": False,
        "model_trained": False,
        "next_action": "Inspect actual .mat channels and official sensor calibration before CSV conversion.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sevenzip", help="Absolute path to 7z.exe if not on PATH")
    args = parser.parse_args(argv)
    try:
        result = inspect_archive(args.archive, sevenzip=args.sevenzip)
    except (SourceVerificationError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "source_unverified", "reason": str(exc),
                          "physical_units_verified": False, "model_trained": False},
                         ensure_ascii=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())