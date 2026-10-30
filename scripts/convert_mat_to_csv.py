"""Paderborn .mat inspection and fail-closed one-recording feature extraction.

A recorded signal is not necessarily in physical SI units. Default inspection
never asserts calibration. CSV conversion requires source-bound unit evidence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from scipy.io import loadmat

FIELDS = ("asset_id", "trial_id", "source_id", "vibration_rms_m_s2", "vibration_peak_m_s2", "current_rms_a", "label", "label_provenance", "license")
VIBRATION = ("vibration_1", "vibration")
CURRENT = ("phase_current_1", "motor_current", "current_1")
PADERBORN_LICENSE = "CC BY-NC 4.0"


def scalar_string(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    if isinstance(value, np.ndarray):
        if value.size == 1:
            return scalar_string(value.item())
        if value.dtype.kind in "US":
            return "".join(str(v) for v in value.ravel()).strip()
    return ""


def fields(obj):
    if isinstance(obj, dict):
        return {k: v for k, v in obj.items() if not k.startswith("__")}
    if hasattr(obj, "_fieldnames"):
        return {k: getattr(obj, k) for k in obj._fieldnames}
    if isinstance(obj, np.void) and obj.dtype.names:
        return {k: obj[k] for k in obj.dtype.names}
    return None


def collect_channels(obj, found: list[dict], depth=0):
    """Walk MATLAB structs/Y records without flattening signal samples into memory."""
    if depth > 15:
        raise ValueError("mat_structure_too_deep")
    mapping = fields(obj)
    if mapping is not None:
        keys = {k.lower(): k for k in mapping}
        # MATLAB Y records carry Name, Data and often an empty Unit.
        if "name" in keys and "data" in keys:
            name = scalar_string(mapping[keys["name"]]).lower()
            if name in VIBRATION + CURRENT:
                unit = scalar_string(mapping[keys["unit"]]) if "unit" in keys else ""
                found.append({"name": name, "unit": unit, "values": mapping[keys["data"]]})
            return
        for key, value in mapping.items():
            lower = key.lower()
            if lower in VIBRATION + CURRENT:
                # Plain numeric signal arrays or nested named records.
                if fields(value) is None and isinstance(value, np.ndarray) and value.dtype.kind in "biuf":
                    found.append({"name": lower, "unit": scalar_string(mapping.get(key + "_unit")), "values": value})
                    continue
            collect_channels(value, found, depth + 1)
        return
    if isinstance(obj, np.ndarray) and (obj.dtype.kind == "O" or obj.dtype.names):
        for item in obj.flat:
            collect_channels(item, found, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            collect_channels(item, found, depth + 1)


def read_channels(path: Path):
    if not path.is_file() or path.suffix.lower() != ".mat":
        raise ValueError("mat_file_missing_or_invalid")
    try:
        data = loadmat(path, squeeze_me=True, struct_as_record=False)
    except (OSError, ValueError, NotImplementedError, TypeError) as exc:
        raise ValueError("unsupported_or_corrupt_mat_file") from exc
    channels = []
    collect_channels(data, channels)
    return channels


def choose(channels, names):
    for name in names:
        matches = [item for item in channels if item["name"] == name]
        if len(matches) > 1:
            raise ValueError(f"ambiguous_channel:{name}")
        if matches:
            return matches[0]
    raise ValueError(f"missing_required_channel:{'/'.join(names)}")


def verify_units(path: Path, vibration, current, manifest_path: Path | None):
    units = (vibration["unit"], current["unit"])
    if units == ("m/s²", "A") or units == ("m/s^2", "A"):
        return "mat_metadata"
    if not manifest_path:
        raise ValueError("unit_metadata_missing_or_unsupported; provide reviewed --unit-manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if manifest.get("source_sha256") != actual:
        raise ValueError("unit_manifest_source_hash_mismatch")
    if manifest.get("vibration_channel") != vibration["name"] or manifest.get("current_channel") != current["name"]:
        raise ValueError("unit_manifest_channel_mismatch")
    if manifest.get("vibration_unit") not in ("m/s²", "m/s^2") or manifest.get("current_unit") != "A":
        raise ValueError("unit_manifest_units_not_si")
    evidence = manifest.get("unit_evidence")
    if not isinstance(evidence, str) or len(evidence.strip()) < 12:
        raise ValueError("unit_manifest_evidence_missing")
    # A human still must verify that the cited source truly establishes these units.
    return evidence.strip()


def as_signal(item):
    values = np.asarray(item["values"])
    if not np.issubdtype(values.dtype, np.number) or np.iscomplexobj(values):
        raise ValueError(f"invalid_signal_dtype:{item['name']}")
    if values.ndim > 2 or (values.ndim == 2 and min(values.shape) > 1):
        raise ValueError(f"invalid_signal_shape:{item['name']}")
    signal = values.reshape(-1).astype(np.float64, copy=False)
    if signal.size < 16 or not np.all(np.isfinite(signal)):
        raise ValueError(f"invalid_signal_values:{item['name']}")
    return signal


def convert(args):
    file = Path(args.mat)
    channels = read_channels(file)
    if args.inspect:
        report = [{"name": c["name"], "unit": c["unit"] or "unknown", "shape": list(np.asarray(c["values"]).shape)} for c in channels]
        print(json.dumps({"file": file.name, "channels": report, "units_verified": False}, ensure_ascii=False, indent=2))
        return
    for name in ("asset_id", "trial_id", "source_id", "label_provenance"):
        value = getattr(args, name)
        if not value or not value.strip() or len(value) > 80:
            raise ValueError(f"missing_or_invalid:{name}")
    if args.label not in ("healthy", "damaged"):
        raise ValueError("invalid_label")
    if args.license != PADERBORN_LICENSE:
        raise ValueError("unsupported_license")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.asset_id):
        raise ValueError("invalid_asset_id")
    if args.asset_id.upper() in {f"K{i:03d}" for i in range(1, 7)} and args.label != "healthy":
        raise ValueError("label_conflicts_with_known_healthy_bearing")
    if args.asset_id.upper().startswith(("KA", "KI", "KB")) and args.label != "damaged":
        raise ValueError("label_conflicts_with_known_damage_bearing")
    # Check the source filename reflects the same physical bearing.
    if not re.search(r"(?:^|_)" + re.escape(args.asset_id) + r"(?:_|\.)", file.name, flags=re.IGNORECASE):
        raise ValueError("asset_id_does_not_match_recording_filename")
    vib = choose(channels, VIBRATION)
    cur = choose(channels, CURRENT)
    unit_evidence = verify_units(file, vib, cur, Path(args.unit_manifest) if args.unit_manifest else None)
    vibration, current = as_signal(vib), as_signal(cur)
    if vibration.size != current.size:
        raise ValueError("signal_sample_count_mismatch")
    vibration_rms = math.sqrt(float(np.mean(vibration * vibration)))
    current_rms = math.sqrt(float(np.mean(current * current)))
    row = dict(zip(FIELDS, (args.asset_id, args.trial_id, args.source_id,
                            vibration_rms, float(np.max(np.abs(vibration))), current_rms,
                            args.label, args.label_provenance, args.license)))
    # Do not overwrite existing records or silently duplicate asset/trial pairs.
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="") as dest:
        writer = csv.DictWriter(dest, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(row)
    print(json.dumps({"output": str(output), "rows": 1, "unit_evidence": unit_evidence,
                      "source_sha256": hashlib.sha256(file.read_bytes()).hexdigest()}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mat", required=True)
    parser.add_argument("--inspect", action="store_true", help="Show channels and raw Unit entries; no CSV written")
    parser.add_argument("--asset-id")
    parser.add_argument("--trial-id")
    parser.add_argument("--source-id")
    parser.add_argument("--label", choices=("healthy", "damaged"))
    parser.add_argument("--label-provenance")
    parser.add_argument("--license", default=PADERBORN_LICENSE)
    parser.add_argument("--unit-manifest", help="Reviewed SHA256-bound units + documentary evidence")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        if not args.inspect and not args.output:
            raise ValueError("missing_output")
        convert(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("CONVERSION_NOT_PUBLISHED:", exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())