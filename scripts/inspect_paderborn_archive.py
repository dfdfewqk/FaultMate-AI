"""Read-only, one-command preflight for one Paderborn bearing RAR archive.

Tests archive integrity with 7-Zip, extracts ONE MATLAB recording into a
throwaway directory, then reports discovered signals and RAW unit metadata.
It never converts to CSV, trains a model, or asserts that signal units are SI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from convert_mat_to_csv import CURRENT, VIBRATION, read_channels, choose


class ArchiveInspectionError(ValueError):
    pass


def find_7zip() -> str:
    for name in ("7z", "7zz", "7za"):
        found = shutil.which(name)
        if found:
            return found
    if os.name == "nt":
        for candidate in (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "7-Zip" / "7z.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "7-Zip" / "7z.exe",
        ):
            if candidate.is_file():
                return str(candidate)
    raise ArchiveInspectionError("7zip_not_found; expected 7z.exe or C:\\Program Files\\7-Zip\\7z.exe")


def archive_members(listing: str) -> list[str]:
    """Parse `7z l -slt -ba` (one Path = entry per file)."""
    paths = []
    for line in listing.splitlines():
        if line.startswith("Path = "):
            name = line[len("Path = "):].strip()
            if name and name.lower().endswith(".mat"):
                paths.append(name)
    return paths


def choose_recording(members: list[str], bearing_id: str) -> str:
    valid = []
    for path in members:
        filename = path.replace("\\", "/").rsplit("/", 1)[-1]
        if re.fullmatch(r"N\d{2}_M\d{2}_F\d{2}_" + re.escape(bearing_id) + r"_\d+\.mat", filename, re.I):
            valid.append(path)
    if not valid:
        raise ArchiveInspectionError(f"no_recording_matching_bearing:{bearing_id}")
    # Deterministic selection independent of archive member ordering.
    return sorted(valid, key=lambda x: (0 if x.lower().endswith(f"_{bearing_id.lower()}_1.mat")
                                           and "n15_m07_f10" in x.lower() else 1, x.lower()))[0]


def invoke_7z(binary: str, *arguments: str) -> str:
    result = subprocess.run([binary, *arguments], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise ArchiveInspectionError(f"7zip_failed:exit={result.returncode}:" + (result.stderr or result.stdout)[-400:])
    return result.stdout


def sha256_stream(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect(archive: Path, binary: str) -> dict:
    archive = archive.resolve()
    if not archive.is_file() or archive.suffix.lower() != ".rar":
        raise ArchiveInspectionError("rar_file_not_found")
    # Check the full compressed archive, not only whether it has a plausible file size.
    invoke_7z(binary, "t", str(archive))
    listing = invoke_7z(binary, "l", "-slt", "-ba", str(archive))
    bearing_id = archive.stem.upper()
    if not re.fullmatch(r"(?:K\d{3}|KA\d{2}|KI\d{2}|KB\d{2})", bearing_id):
        raise ArchiveInspectionError("unsupported_bearing_archive_name")
    members = archive_members(listing)
    selected = choose_recording(members, bearing_id)
    filename = selected.replace("\\", "/").rsplit("/", 1)[-1]
    with tempfile.TemporaryDirectory(prefix="faultmate-mat-inspection-") as temporary:
        output_dir = Path(temporary)
        # 'e' discards archive directory paths. Never overwrite an existing user file.
        invoke_7z(binary, "e", "-y", f"-o{output_dir}", str(archive), selected)
        extracted = output_dir / filename
        if not extracted.is_file():
            raise ArchiveInspectionError("selected_mat_not_extracted")
        channels = read_channels(extracted)
        summary = [
            {"name": c["name"], "unit_as_recorded": c["unit"] or "unknown", "shape": list(getattr(c["values"], "shape", ())) }
            for c in channels
        ]
        try:
            vibration = choose(channels, VIBRATION)
            current = choose(channels, CURRENT)
            matched = {"vibration": vibration["name"], "current": current["name"]}
        except ValueError as exc:
            matched = {"error": str(exc)}
        status = "raw_channels_found_units_require_source_review" if "error" not in matched else "required_channel_missing"
        return {
            "status": status,
            "archive": archive.name,
            "archive_sha256": sha256_stream(archive),
            "archive_integrity": "7zip_test_passed",
            "recording_count_mat": len(members),
            "inspected_recording": selected,
            "recording_sha256": sha256_stream(extracted),
            "channels": summary,
            "matched": matched,
            "physical_units_verified": False,
            "csv_generated": False,
            "model_trained": False,
            "next_action": "Compare raw unit metadata and official sensor calibration documentation before conversion.",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, help="Path to a downloaded K001.rar or another official bearing archive")
    parser.add_argument("--sevenzip", help="Optional full path to 7z.exe")
    args = parser.parse_args()
    try:
        result = inspect(Path(args.archive), args.sevenzip or find_7zip())
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["status"] == "raw_channels_found_units_require_source_review" else 2
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "inspection_failed", "error": str(exc),
                          "physical_units_verified": False, "csv_generated": False}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
