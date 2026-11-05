"""Fail-closed sensor-unit provenance gate for Paderborn .mat features.

This module does NOT infer measurement units from channel names or sensor types.
It refuses physical-unit CSV eligibility until per-channel primary evidence,
calibration, raw-file identity and human review are present. It never outputs
training CSV or uploads a file.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

CHANNELS = {"vibration_1": "m/s^2", "phase_current_1": "A"}
SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_finite_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _safe_evidence_path(root: Path, name: Any) -> Path:
    if not isinstance(name, str) or not name.strip() or "\\" in name:
        raise ValueError("invalid_evidence_path")
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("unsafe_evidence_path")
    resolved_root = root.resolve(strict=True)
    resolved = (resolved_root / path).resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(resolved_root):
        raise ValueError("evidence_file_outside_root")
    return resolved


def _channel_errors(name: str, item: Any, evidence_root: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return [f"{name}:missing_channel_config"]
    target = CHANNELS[name]
    if item.get("target_unit") != target:
        errors.append(f"{name}:wrong_target_unit")
    mode = item.get("mode")
    if mode not in ("already_physical", "calibrated_voltage"):
        errors.append(f"{name}:unverified_source_unit")
    elif mode == "already_physical":
        if item.get("source_unit") != target:
            errors.append(f"{name}:unsupported_source_unit")
    elif item.get("source_unit") != "V":
        errors.append(f"{name}:voltage_source_unit_required")
    if mode == "calibrated_voltage":
        if (not _is_finite_number(item.get("sensitivity_v_per_unit"))
                or item["sensitivity_v_per_unit"] <= 0):
            errors.append(f"{name}:missing_positive_sensitivity")
        if not _is_finite_number(item.get("zero_offset_v")):
            errors.append(f"{name}:missing_zero_offset")
    proof = item.get("evidence")
    if not isinstance(proof, dict):
        return errors + [f"{name}:missing_primary_evidence"]
    if not isinstance(proof.get("source_url"), str) or not proof["source_url"].startswith("https://"):
        errors.append(f"{name}:missing_source_url")
    expected = proof.get("sha256")
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        errors.append(f"{name}:missing_evidence_digest")
    try:
        doc = _safe_evidence_path(evidence_root, proof.get("file"))
        if isinstance(expected, str) and SHA256.fullmatch(expected):
            if digest_file(doc) != expected.lower():
                errors.append(f"{name}:evidence_digest_mismatch")
    except (OSError, ValueError):
        errors.append(f"{name}:evidence_file_not_verified")
    if not isinstance(proof.get("calibration_scope"), str) or len(proof["calibration_scope"].strip()) < 12:
        errors.append(f"{name}:missing_measurement_chain_scope")
    return errors


def evaluate_manifest(manifest: Any, evidence_root: Path, mat_path: Path | None) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return {"status": "blocked", "physical_csv_allowed": False, "errors": ["invalid_manifest"]}
    if manifest.get("dataset") != "paderborn_bearing_datacenter":
        errors.append("unexpected_dataset")
    if not re.fullmatch(r"(K00[1-6]|KA\d{2}|KB\d{2}|KI\d{2})", str(manifest.get("asset_id", ""))):
        errors.append("invalid_asset_id")
    expected_raw = manifest.get("raw_mat_sha256")
    if not isinstance(expected_raw, str) or not SHA256.fullmatch(expected_raw):
        errors.append("missing_raw_mat_digest")
    if mat_path is None:
        errors.append("raw_mat_not_checked")
    else:
        try:
            if not mat_path.is_file() or mat_path.suffix.lower() != ".mat":
                raise OSError("not_mat")
            if isinstance(expected_raw, str) and SHA256.fullmatch(expected_raw):
                if digest_file(mat_path) != expected_raw.lower():
                    errors.append("raw_mat_digest_mismatch")
        except OSError:
            errors.append("raw_mat_unavailable")
    channels = manifest.get("channels")
    if not isinstance(channels, dict):
        errors.append("channels_missing")
        channels = {}
    for channel in CHANNELS:
        errors.extend(_channel_errors(channel, channels.get(channel), evidence_root))
    review = manifest.get("physical_unit_review")
    if not isinstance(review, dict) or review.get("approved") is not True:
        errors.append("human_unit_review_required")
    else:
        if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
            errors.append("reviewer_missing")
        try:
            reviewed = datetime.fromisoformat(str(review.get("reviewed_utc", "")).replace("Z", "+00:00"))
            if reviewed.tzinfo is None or reviewed.utcoffset() != timezone.utc.utcoffset(reviewed):
                raise ValueError("not_utc")
        except ValueError:
            errors.append("invalid_review_timestamp")
    return {
        "status": "ready_for_physical_csv" if not errors else "blocked",
        "physical_csv_allowed": not errors,
        "asset_id": manifest.get("asset_id"),
        "errors": sorted(set(errors)),
        "fallback": None if not errors else "retain_raw_signal_and_metadata_only_no_physical_csv_or_ml_training",
    }


def convert_samples_to_physical(values: list[float], channel: dict[str, Any], expected_unit: str) -> list[float]:
    """Only call after evaluate_manifest(...).physical_csv_allowed is true."""
    if channel.get("target_unit") != expected_unit or expected_unit not in CHANNELS.values():
        raise ValueError("target_unit_mismatch")
    mode = channel.get("mode")
    if mode == "already_physical" and channel.get("source_unit") == expected_unit:
        output = values
    elif mode == "calibrated_voltage" and channel.get("source_unit") == "V":
        scale = channel.get("sensitivity_v_per_unit")
        offset = channel.get("zero_offset_v")
        if not _is_finite_number(scale) or scale <= 0 or not _is_finite_number(offset):
            raise ValueError("unverified_calibration")
        output = [(v - offset) / scale for v in values]
    else:
        raise ValueError("unverified_physical_unit")
    if not all(_is_finite_number(v) and math.isfinite(v) for v in output):
        raise ValueError("invalid_samples")
    return list(output)


def main() -> int:
    ap = argparse.ArgumentParser(description="Check physical-unit evidence before MAT->feature CSV")
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--mat", type=Path, default=None)
    ap.add_argument("--evidence-root", required=True, type=Path)
    args = ap.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = evaluate_manifest(manifest, args.evidence_root, args.mat)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        result = {"status": "blocked", "physical_csv_allowed": False, "errors": [f"manifest_unreadable:{type(exc).__name__}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["physical_csv_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
