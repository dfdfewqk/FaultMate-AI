"""Read-only provenance and duplicate audit for REAL Paderborn recordings.

The recorded MAT 'Unit' entries may be blank. This tool deliberately does NOT
convert raw amplitudes to SI, generate model-ready CSV, fit or publish a model.
Use one verified RAR at a time; no raw signal data are uploaded or persisted.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_paderborn_assets import (
    CATALOG, OFFICIAL_CONDITIONS, SourceAuditError,
    archive_inventory, archive_md5, validate_catalog,
)
from scripts.convert_mat_to_csv import VIBRATION, CURRENT, as_signal, choose, read_channels


def raw_signal_fingerprint(vibration: np.ndarray, current: np.ndarray) -> str:
    """Hash both numeric sample sequences, including lengths; never hash filenames."""
    if vibration.ndim != 1 or current.ndim != 1 or vibration.size != current.size:
        raise SourceAuditError("paired_signal_shape_mismatch")
    if vibration.size < 16 or not np.all(np.isfinite(vibration)) or not np.all(np.isfinite(current)):
        raise SourceAuditError("invalid_raw_signal")
    digest = hashlib.sha256()
    for channel_name, signal in (("vibration_1", vibration), ("phase_current_1", current)):
        values = np.asarray(signal, dtype="<f8").copy()
        # Hashing must not distinguish +0.0 from -0.0, which are numerically equal.
        values[values == 0] = 0
        digest.update(channel_name.encode("ascii") + b"\x00")
        digest.update(struct.pack("<Q", values.size))
        digest.update(values.tobytes())
    return digest.hexdigest()


def describe_mat(path: Path, expected_name: str) -> dict:
    """Describe numeric raw features, with NO physical-unit claim."""
    channels = read_channels(path)
    vib, cur = choose(channels, VIBRATION), choose(channels, CURRENT)
    vibration, current = as_signal(vib), as_signal(cur)
    if vibration.size != current.size:
        raise SourceAuditError("paired_signal_shape_mismatch")
    fingerprint = raw_signal_fingerprint(vibration, current)
    return {
        "recording": expected_name,
        "mat_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "raw_signal_fingerprint": fingerprint,
        "sample_count": int(vibration.size),
        "vibration_channel": vib["name"],
        "current_channel": cur["name"],
        "raw_vibration_unit": vib["unit"] or "unknown",
        "raw_current_unit": cur["unit"] or "unknown",
        "raw_rms_vibration_unscaled": float(np.sqrt(np.mean(vibration * vibration))),
        "raw_peak_abs_vibration_unscaled": float(np.max(np.abs(vibration))),
        "raw_rms_current_unscaled": float(np.sqrt(np.mean(current * current))),
    }


def audit_one_archive(archive: Path, bearing_id: str,
                      *, sevenzip: str, trials: tuple[int, ...] = (1, 17, 18),
                      catalog_path: Path = CATALOG) -> dict:
    if archive.is_symlink() or not archive.is_file() or archive.name.lower() != f"{bearing_id.lower()}.rar":
        raise SourceAuditError("wrong_or_missing_source_archive")
    entries = {
        item["id"]: item
        for item in validate_catalog(json.loads(catalog_path.read_text(encoding="utf-8")))
    }
    source = entries.get(bearing_id)
    if source is None:
        raise SourceAuditError("unknown_bearing_code")
    if not trials or len(set(trials)) != len(trials) or any(i < 1 or i > 20 for i in trials):
        raise SourceAuditError("invalid_selected_trials")
    if archive.stat().st_size < 100_000_000 or archive_md5(archive) != source["md5"]:
        raise SourceAuditError("official_source_md5_mismatch")
    checked = subprocess.run([sevenzip, "t", str(archive)], capture_output=True,
                             timeout=240, check=False)
    if checked.returncode != 0:
        raise SourceAuditError(f"archive_integrity_failed:{checked.returncode}")
    listing = subprocess.run([sevenzip, "l", "-slt", "-ba", str(archive)],
                             capture_output=True, timeout=60, check=False)
    if listing.returncode != 0:
        raise SourceAuditError("archive_listing_failed")
    listed = listing.stdout.decode("utf-8", errors="replace")
    archive_inventory(listed, bearing_id)  # requires 80 real files, 4 conditions × 20
    members = [line[7:].strip() for line in listed.splitlines() if line.startswith("Path = ")]
    entries_by_basename: dict[str, list[str]] = defaultdict(list)
    for member in members:
        entries_by_basename[member.replace("\\", "/").rsplit("/", 1)[-1]].append(member)

    selected = []
    for condition in sorted(OFFICIAL_CONDITIONS):
        for trial in sorted(trials):
            expected = f"{condition}_{bearing_id}_{trial}.mat"
            matches = entries_by_basename.get(expected, [])
            if len(matches) != 1:
                raise SourceAuditError(f"recording_missing_or_ambiguous:{expected}")
            selected.append((expected, matches[0], condition, trial))

    details = []
    fingerprint_first_recording: dict[str, str] = {}
    duplicates = []
    # A fresh extraction folder for every member avoids collisions and persists
    # no MAT files once this read-only audit exits.
    with tempfile.TemporaryDirectory(prefix="faultmate-paderborn-audit-") as temp_root:
        temp = Path(temp_root)
        for index, (expected, member, condition, trial) in enumerate(selected):
            destination = temp / str(index)
            destination.mkdir()
            result = subprocess.run(
                [sevenzip, "e", "-y", f"-o{destination}", str(archive), member],
                capture_output=True, timeout=90, check=False,
            )
            if result.returncode != 0:
                raise SourceAuditError(f"member_extraction_failed:{expected}")
            path = destination / expected
            if not path.is_file():
                raise SourceAuditError(f"member_missing_after_extraction:{expected}")
            info = describe_mat(path, expected)
            info["condition"] = condition
            info["trial"] = trial
            fingerprint = info["raw_signal_fingerprint"]
            if fingerprint in fingerprint_first_recording:
                info["duplicate_of"] = fingerprint_first_recording[fingerprint]
                duplicates.append({"recording": expected, "duplicate_of": info["duplicate_of"]})
            else:
                fingerprint_first_recording[fingerprint] = expected
                info["duplicate_of"] = None
            details.append(info)
            path.unlink()
    return {
        "status": "source_verified_raw_units_unapproved",
        "bearing_id": bearing_id,
        "source_md5_verified": True,
        "archive_inventory_verified": "80_mat_files_across_4_conditions",
        "license": source["license"] if "license" in source else "CC BY-NC 4.0",
        "label": source["label"],
        "label_evidence": "Lessmeier et al. 2016 bearing identity tables; curated catalog",
        "inspected_recordings": len(details),
        "unique_raw_signals": len(fingerprint_first_recording),
        "duplicate_raw_recordings": duplicates,
        "recordings": details,
        "raw_units_verified": False,
        "si_csv_generated": False,
        "ml_trained": False,
        "model_activated": False,
        "approved_for_training": False,
        "limitations": "Numerical raw signal values are NOT certified in A or m/s^2.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--bearing-id", required=True)
    parser.add_argument("--trials", nargs="+", type=int, default=[1, 17, 18])
    parser.add_argument("--all-recordings", action="store_true")
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--sevenzip")
    parser.add_argument("--out", type=Path, help="Optional new JSON audit file; never overwrites")
    args = parser.parse_args(argv)
    executable = args.sevenzip or shutil.which("7z") or shutil.which("7zz")
    if executable is None and sys.platform == "win32":
        candidate = Path(r"C:\Program Files\7-Zip\7z.exe")
        if candidate.is_file():
            executable = str(candidate)
    try:
        if not executable:
            raise SourceAuditError("sevenzip_not_installed")
        selected_trials = tuple(range(1, 21)) if args.all_recordings else tuple(args.trials)
        report = audit_one_archive(
            args.archive.absolute(), args.bearing_id.upper(), sevenzip=executable,
            trials=selected_trials, catalog_path=args.catalog,
        )
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as handle:
                handle.write(encoded)
        print(encoded)
    except (ValueError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "audit_failed_no_result_published", "reason": str(exc),
                          "approved_for_training": False}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
