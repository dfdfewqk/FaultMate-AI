"""Source-bound, SI-unit-independent Paderborn feature extraction.

Reads an original verified RAR (one of 12 catalogued bearings), checks its
official MD5 and 80-file inventory, and extracts scale/offset-invariant shape
features from actual vibration_1 and phase_current_1 samples.

This is a deliberately SEPARATE EXPERIMENTAL path from the SI-calibrated
scripts/convert_mat_to_csv.py and train_ml.py. No amplitude, A or m/s² is
inferred. No trained model is activated. No raw measurements are published.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_paderborn_assets import (
    CATALOG, OFFICIAL_CONDITIONS, SourceAuditError, archive_inventory,
    archive_md5, validate_catalog,
)
from scripts.audit_paderborn_raw_recordings import raw_signal_fingerprint
from scripts.convert_mat_to_csv import VIBRATION, CURRENT, read_channels, choose, as_signal

SCHEMA = "faultmate_unitless_raw_shape_v1"
WINDOW = 16384
FEATURE_NAMES = tuple(
    f"{ch}_{name}"
    for ch in ("vibration", "current")
    for name in ("kurtosis", "crest", "abs_q95_over_q50",
                 "spectral_entropy", "spectral_high_ratio", "zero_crossing_ratio")
)
HEX = re.compile(r"^[0-9a-f]{64}$")


def shape_features(raw: np.ndarray) -> list[float]:
    """Twelve dimensionless features, insensitive to nonzero gain/DC offset.

    The same three non-overlapping (when long enough) windows are sampled
    from each source recording. FFT bands are fractions of Nyquist, not Hz.
    They are not physical unit calibration and are not bearing fault labels.
    """
    x = np.asarray(raw, dtype=np.float64).reshape(-1)
    if len(x) < WINDOW or not np.all(np.isfinite(x)):
        raise SourceAuditError("invalid_raw_signal_for_unitless_features")
    starts = [0, (len(x) - WINDOW) // 2, len(x) - WINDOW]
    windows = []
    for start in starts:
        v = x[start:start + WINDOW].copy()
        v -= np.mean(v)
        scale = np.sqrt(np.mean(v * v))
        if not np.isfinite(scale) or scale < 1e-20:
            raise SourceAuditError("constant_or_unusable_signal")
        v /= scale
        absolute = np.abs(v)
        median_abs = float(np.quantile(absolute, .50))
        if median_abs < 1e-12:
            raise SourceAuditError("invalid_absolute_quantile")
        p95 = float(np.quantile(absolute, .95))
        # Multiplying by the Hann window suppresses the DC discontinuity.
        spectrum = np.abs(np.fft.rfft(v * np.hanning(len(v)))) ** 2
        spectrum[0] = 0.
        power = float(np.sum(spectrum))
        if not np.isfinite(power) or power <= 0:
            raise SourceAuditError("invalid_spectral_power")
        norm_power = spectrum / power
        # Entropy normalized to [0,1], independent of amplitude or signal units.
        positive = norm_power[norm_power > 0]
        entropy = float(-np.sum(positive * np.log(positive))
                        / np.log(len(norm_power) - 1))
        frac_high = float(np.sum(norm_power[len(norm_power) // 2:]))
        windows.append([
            float(np.mean(v ** 4)),
            float(np.max(absolute)),
            float(p95 / median_abs),
            entropy,
            frac_high,
            float(np.count_nonzero((v[:-1] < 0) != (v[1:] < 0))
                  / (len(v) - 1)),
        ])
    return [float(z) for z in np.median(np.asarray(windows), axis=0)]


def record_features(vibration: np.ndarray, current: np.ndarray) -> list[float]:
    if vibration.ndim != 1 or current.ndim != 1 or len(vibration) != len(current):
        raise SourceAuditError("paired_channels_invalid")
    a = shape_features(vibration) + shape_features(current)
    if len(a) != len(FEATURE_NAMES) or not np.all(np.isfinite(a)):
        raise SourceAuditError("unitless_feature_invalid")
    return a


def extract_archive(
    archive: Path, bearing_id: str, *, sevenzip: str, catalog_path: Path = CATALOG
) -> dict:
    if (archive.is_symlink() or not archive.is_file()
            or archive.name.lower() != f"{bearing_id.lower()}.rar"):
        raise SourceAuditError("wrong_or_missing_archive")
    document = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog = {row["id"]: row for row in validate_catalog(document)}
    if bearing_id not in catalog:
        raise SourceAuditError("bearing_not_in_approved_source_cohort")
    row = catalog[bearing_id]
    if archive.stat().st_size < 100_000_000 or archive_md5(archive) != row["md5"]:
        raise SourceAuditError("official_source_md5_mismatch")
    check = subprocess.run([sevenzip, "t", str(archive)],
                           capture_output=True, timeout=240, check=False)
    if check.returncode:
        raise SourceAuditError("archive_integrity_test_failed")
    listing = subprocess.run([sevenzip, "l", "-slt", "-ba", str(archive)],
                             capture_output=True, timeout=60, check=False)
    if listing.returncode:
        raise SourceAuditError("archive_listing_failed")
    text = listing.stdout.decode("utf-8", errors="replace")
    archive_inventory(text, bearing_id)
    members: dict[str, list[str]] = defaultdict(list)
    for line in text.splitlines():
        if line.startswith("Path = "):
            member = line[7:].strip()
            members[member.replace("\\", "/").rsplit("/", 1)[-1]].append(member)

    records = []
    seen_fingerprints = {}
    duplicates = []
    with tempfile.TemporaryDirectory(prefix="faultmate-unitless-raw-") as t:
        temp = Path(t)
        for condition in sorted(OFFICIAL_CONDITIONS):
            for trial in range(1, 21):
                filename = f"{condition}_{bearing_id}_{trial}.mat"
                matches = members.get(filename, [])
                if len(matches) != 1:
                    raise SourceAuditError("missing_or_duplicate_mat_member:" + filename)
                dest = temp / f"{condition}_{trial}"
                dest.mkdir()
                result = subprocess.run(
                    [sevenzip, "e", "-y", f"-o{dest}", str(archive), matches[0]],
                    capture_output=True, timeout=90, check=False)
                if result.returncode:
                    raise SourceAuditError("mat_extraction_failed:" + filename)
                mat = dest / filename
                if not mat.is_file():
                    raise SourceAuditError("mat_member_missing_after_extract:" + filename)
                source_mat_sha256 = hashlib.sha256(mat.read_bytes()).hexdigest()
                channels = read_channels(mat)
                vib = choose(channels, VIBRATION)
                cur = choose(channels, CURRENT)
                vibration, current = as_signal(vib), as_signal(cur)
                if len(vibration) != len(current):
                    raise SourceAuditError("paired_signal_length_mismatch")
                fingerprint = raw_signal_fingerprint(vibration, current)
                duplicate_of = seen_fingerprints.get(fingerprint)
                if duplicate_of:
                    duplicates.append({"recording": filename, "duplicate_of": duplicate_of})
                    values = None
                else:
                    seen_fingerprints[fingerprint] = filename
                    values = record_features(vibration, current)
                records.append({
                    "recording": filename, "condition": condition,
                    "trial": trial, "source_mat_sha256": source_mat_sha256,
                    "source_raw_signal_fingerprint": fingerprint,
                    "sample_count": int(vibration.size),
                    "duplicate_of": duplicate_of, "values": values,
                })
                mat.unlink()
    assert len(records) == 80
    return {
        "schema": SCHEMA, "status": "real_raw_unitless_features_unreviewed",
        "dataset": "paderborn_bearing_datacenter", "bearing_id": bearing_id,
        "label": row["label"], "license": document["license"],
        "official_archive_md5": row["md5"], "archive_verified": True,
        "source_catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "source_recording_count": len(records),
        "unique_recording_count": len(seen_fingerprints),
        "duplicates": duplicates, "feature_names": FEATURE_NAMES,
        "raw_si_units_verified": False, "si_amplitudes_used": False,
        "ml_trained": False, "approved_for_runtime": False,
        "records": records,
        "warning": "Unitless raw shape features, not calibrated acceleration/current.",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--bearing-id", required=True)
    p.add_argument("--catalog", type=Path, default=CATALOG)
    p.add_argument("--sevenzip")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    zip7 = args.sevenzip or shutil.which("7z") or shutil.which("7zz")
    if not zip7 and sys.platform == "win32":
        candidate = Path(r"C:\Program Files\7-Zip\7z.exe")
        if candidate.is_file():
            zip7 = str(candidate)
    try:
        if not zip7:
            raise SourceAuditError("7zip_not_available")
        report = extract_archive(args.archive.absolute(), args.bearing_id.upper(),
                                 sevenzip=zip7, catalog_path=args.catalog)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        print(json.dumps({
            "status": report["status"], "bearing_id": report["bearing_id"],
            "records": report["source_recording_count"],
            "unique": report["unique_recording_count"],
            "duplicates": len(report["duplicates"]),
            "physical_units_verified": False, "trained": False,
        }))
    except (OSError, ValueError, subprocess.SubprocessError,
            json.JSONDecodeError) as exc:
        print("UNITLESS_EXTRACTION_FAILED_NO_OUTPUT:", str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
