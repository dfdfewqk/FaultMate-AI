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
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

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


def verify_units(path: Path, vibration, current, manifest_path: Path | None,
                 evidence_document: Path | None = None):
    """Return (evidence, vib scale, current scale, vib offset, current offset).

    Empty Unit fields can only be overridden with a source-MAT-bound calibration
    review and a *local evidence document* whose SHA-256 is pinned. A sensor
    model or an arbitrary review note alone is NOT calibration evidence.

    This validates the human review trail, not the factual truth of the document.
    """
    units = (vibration["unit"], current["unit"])
    if units in (("m/s²", "A"), ("m/s^2", "A")):
        return "mat_metadata", 1.0, 1.0, 0.0, 0.0
    if not manifest_path:
        raise ValueError("unit_metadata_missing_or_unsupported; provide reviewed --unit-manifest")
    if evidence_document is None:
        raise ValueError("unit_evidence_document_required")
    if evidence_document.is_symlink() or not evidence_document.is_file():
        raise ValueError("unit_evidence_document_missing_or_symlink")
    if evidence_document.suffix.lower() not in (".pdf", ".txt", ".md", ".eml"):
        raise ValueError("unit_evidence_document_type_not_supported")
    if not 100 <= evidence_document.stat().st_size <= 20_000_000:
        raise ValueError("unit_evidence_document_size_invalid")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("unit_manifest_must_be_object")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if manifest.get("source_sha256") != actual:
        raise ValueError("unit_manifest_source_hash_mismatch")
    if manifest.get("vibration_channel") != vibration["name"] or manifest.get("current_channel") != current["name"]:
        raise ValueError("unit_manifest_channel_mismatch")
    if manifest.get("vibration_unit") not in ("m/s²", "m/s^2") or manifest.get("current_unit") != "A":
        raise ValueError("unit_manifest_units_not_si")
    if manifest.get("evidence_document_sha256") != hashlib.sha256(evidence_document.read_bytes()).hexdigest():
        raise ValueError("unit_evidence_document_hash_mismatch")
    if manifest.get("stored_mat_values_calibration_verified") is not True:
        raise ValueError("stored_numeric_calibration_not_verified")
    if manifest.get("evidence_type") not in ("primary_dataset_documentation", "dataset_author_confirmation"):
        raise ValueError("dataset_specific_evidence_required")
    url = manifest.get("evidence_url")
    if not isinstance(url, str) or urlparse(url).scheme != "https" or not urlparse(url).hostname:
        raise ValueError("unit_evidence_source_url_required")
    # The review must explain the numerical scaling of values in the *stored*
    # MAT channels, not just quote the model/sensitivity of a sensor.
    explanation = manifest.get("unit_evidence")
    if not isinstance(explanation, str) or len(explanation.strip()) < 40:
        raise ValueError("unit_evidence_specific_explanation_required")
    location = manifest.get("evidence_location")
    if not isinstance(location, str) or len(location.strip()) < 3:
        raise ValueError("unit_evidence_page_or_section_required")
    reviewer = manifest.get("reviewed_by")
    if not isinstance(reviewer, str) or len(reviewer.strip()) < 2:
        raise ValueError("independent_reviewer_required")
    stamp = manifest.get("reviewed_utc")
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("dated_calibration_review_required") from exc
    factors = []
    for name in ("vibration_scale_to_m_s2", "current_scale_to_a"):
        raw = manifest.get(name)
        if type(raw) not in (int, float) or not math.isfinite(raw) or raw <= 0:
            raise ValueError("invalid_calibration_scale:" + name)
        factors.append(float(raw))
    # Conversion is affine, not just a multiplier. The LEM CKSR sensor can
    # produce a 2.5 V zero-current reference; blindly multiplying a raw
    # voltage by A/V would invent a large DC current. Reject missing offsets.
    stored_units = []
    offsets = []
    for channel, allowed, stored_key, offset_key in (
        (vibration, ("m/s²", "m/s^2", "g", "V", "mV"),
         "vibration_stored_unit", "vibration_offset_in_stored_unit"),
        (current, ("A", "V", "mV"),
         "current_stored_unit", "current_offset_in_stored_unit"),
    ):
        stored = manifest.get(stored_key)
        if stored not in allowed:
            raise ValueError("stored_input_unit_missing_or_invalid:" + stored_key)
        declared = channel["unit"]
        if declared not in ("", "unknown") and declared.replace("m/s^2", "m/s²") != stored.replace("m/s^2", "m/s²"):
            raise ValueError("stored_input_unit_mismatch_with_mat")
        raw_offset = manifest.get(offset_key)
        if type(raw_offset) not in (int, float) or not math.isfinite(raw_offset):
            raise ValueError("stored_input_offset_missing_or_invalid:" + offset_key)
        stored_units.append(stored)
        offsets.append(float(raw_offset))
    if stored_units[0] in ("m/s²", "m/s^2") and (factors[0] != 1.0 or offsets[0] != 0.0):
        raise ValueError("vibration_si_scale_offset_conflict")
    if stored_units[0] == "g" and not math.isclose(factors[0], 9.80665, rel_tol=1e-7):
        raise ValueError("g_to_m_s2_scale_incorrect")
    if stored_units[1] == "A" and (factors[1] != 1.0 or offsets[1] != 0.0):
        raise ValueError("current_si_scale_offset_conflict")
    # Do not accept a reviewer overriding a *known* incompatible MAT unit.
    if vibration["unit"] not in ("", "unknown", "V", "mV", "g", "m/s²", "m/s^2"):
        raise ValueError("unsupported_vibration_mat_unit")
    if current["unit"] not in ("", "unknown", "V", "mV", "A"):
        raise ValueError("unsupported_current_mat_unit")
    if vibration["unit"] in ("m/s²", "m/s^2") and factors[0] != 1.0:
        raise ValueError("vibration_si_metadata_scale_conflict")
    if current["unit"] == "A" and factors[1] != 1.0:
        raise ValueError("current_si_metadata_scale_conflict")
    return explanation.strip(), factors[0], factors[1], offsets[0], offsets[1]

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
    unit_evidence, vibration_scale, current_scale, vibration_offset, current_offset = verify_units(
        file, vib, cur,
        Path(args.unit_manifest) if args.unit_manifest else None,
        Path(args.unit_evidence_document) if getattr(args, "unit_evidence_document", None) else None,
    )
    vibration = (as_signal(vib) - vibration_offset) * vibration_scale
    current = (as_signal(cur) - current_offset) * current_scale
    if not np.all(np.isfinite(vibration)) or not np.all(np.isfinite(current)):
        raise ValueError("invalid_calibrated_signal")
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
    parser.add_argument("--unit-manifest", help="MAT-bound human calibration review JSON (not proof by itself)")
    parser.add_argument("--unit-evidence-document", help="Locally stored primary calibration document or author response, hash-bound to review")
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