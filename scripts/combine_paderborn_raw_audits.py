"""Combine source-verified Paderborn raw audit JSONs without claiming SI units.

This is a read-only pre-training provenance check. It cannot approve calibration,
produce CSV features, fit a model, upload raw measurements or deploy anything.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_paderborn_assets import CATALOG, CONDITION, OFFICIAL_CONDITIONS, SourceAuditError, validate_catalog

HEX64 = re.compile(r"[a-f0-9]{64}\Z")


def _digest(value: object) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def combine_audits(reports_dir: Path, catalog_path: Path = CATALOG) -> dict:
    """Fail on spoofed, untraced, internally inconsistent or cross-asset records."""
    if reports_dir.is_symlink() or not reports_dir.is_dir():
        raise SourceAuditError("audit_reports_directory_missing_or_symlink")
    catalog_data = catalog_path.read_bytes()
    official = {row["id"]: row for row in validate_catalog(json.loads(catalog_data))}
    catalog_digest = hashlib.sha256(catalog_data).hexdigest()
    files = sorted(reports_dir.glob("*.json"))
    if not files:
        raise SourceAuditError("no_raw_audit_reports")
    if len(files) > len(official):
        raise SourceAuditError("too_many_audit_reports")

    seen_assets = set()
    fingerprints: dict[str, tuple[str, str]] = {}
    duplicates = []
    counts = Counter()
    data_files = 0

    for path in files:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 5_000_000:
            raise SourceAuditError("invalid_raw_audit_file")
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise SourceAuditError("raw_audit_not_a_json_object")
        bearing = report.get("bearing_id")
        if bearing not in official or bearing in seen_assets:
            raise SourceAuditError("unexpected_or_duplicate_bearing_audit")
        source = official[bearing]
        if (report.get("status") != "source_verified_raw_units_unapproved"
            or report.get("source_md5_verified") is not True
            or report.get("source_archive_md5") != source["md5"]
            or report.get("source_catalog_sha256") != catalog_digest
            or not isinstance(report.get("source_archive_size_bytes"), int)
            or report["source_archive_size_bytes"] < 100_000_000
            or report.get("archive_inventory_verified") != "80_mat_files_across_4_conditions"
            or report.get("label") != source["label"]
            or report.get("license") != "CC BY-NC 4.0"):
            raise SourceAuditError(f"source_provenance_invalid:{bearing}")
        for flag in ("raw_units_verified", "si_csv_generated", "ml_trained",
                     "model_activated", "approved_for_training"):
            if report.get(flag) is not False:
                raise SourceAuditError(f"unexpected_training_or_unit_claim:{bearing}:{flag}")

        recordings = report.get("recordings")
        if (not isinstance(recordings, list) or not recordings
            or len(recordings) != report.get("inspected_recordings")):
            raise SourceAuditError("recording_inventory_invalid")
        local_names = set()
        local_first = {}
        expected_duplicates = []
        for record in recordings:
            if not isinstance(record, dict):
                raise SourceAuditError("invalid_raw_record")
            name = record.get("recording")
            match = CONDITION.fullmatch(name) if isinstance(name, str) else None
            if (match is None or match.group(2).upper() != bearing
                or match.group(1).upper() not in OFFICIAL_CONDITIONS
                or name in local_names
                or record.get("condition") != match.group(1).upper()
                or record.get("trial") != int(match.group(3))
                or not (1 <= int(match.group(3)) <= 20)):
                raise SourceAuditError(f"recording_identity_invalid:{bearing}")
            local_names.add(name)
            fingerprint = record.get("raw_signal_fingerprint")
            if (not _digest(fingerprint) or not _digest(record.get("mat_sha256"))
                or type(record.get("sample_count")) is not int
                or record["sample_count"] < 16):
                raise SourceAuditError("signal_fingerprint_invalid")
            for metric in ("raw_rms_vibration_unscaled", "raw_peak_abs_vibration_unscaled",
                           "raw_rms_current_unscaled"):
                value = record.get(metric)
                if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
                    raise SourceAuditError("invalid_unscaled_signal_metric")
            if record["raw_peak_abs_vibration_unscaled"] + 1e-10 < record["raw_rms_vibration_unscaled"]:
                raise SourceAuditError("raw_peak_smaller_than_rms")
            if fingerprint in fingerprints and fingerprints[fingerprint][0] != bearing:
                raise SourceAuditError("identical_raw_signal_across_bearings")
            fingerprints.setdefault(fingerprint, (bearing, name))
            first = local_first.setdefault(fingerprint, name)
            if first != name:
                expected_duplicates.append({"recording": name, "duplicate_of": first})
                if record.get("duplicate_of") != first:
                    raise SourceAuditError("duplicate_record_link_invalid")
            elif record.get("duplicate_of") is not None:
                raise SourceAuditError("false_duplicate_claim")
        if (report.get("unique_raw_signals") != len(local_first)
            or report.get("duplicate_raw_recordings") != expected_duplicates):
            raise SourceAuditError("duplicate_summary_invalid")
        duplicates.extend({"bearing_id": bearing, **item} for item in expected_duplicates)
        data_files += len(recordings)
        counts[source["label"]] += 1
        seen_assets.add(bearing)

    missing = sorted(set(official) - seen_assets)
    return {
        "status": "raw_audit_partial" if missing else "raw_archives_audited_calibration_unverified",
        "source_catalog_sha256": catalog_digest,
        "verified_independent_bearings": len(seen_assets),
        "verified_by_label": {key: counts[key] for key in ("healthy", "damaged")},
        "bearings_missing_audit": missing,
        "inspected_recordings": data_files,
        "duplicate_raw_recordings": duplicates,
        "unique_raw_signals_in_inspected_recordings": len(fingerprints),
        "minimum_bearing_counts_met": counts["healthy"] >= 5 and counts["damaged"] >= 5,
        "physical_units_verified": False,
        "si_csv_generated": False,
        "model_trained": False,
        "model_activated": False,
        "training_permitted": False,
        "blocking_reason": "No source-proven scale for Paderborn MAT raw sensor values in m/s^2 and A.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", required=True, type=Path)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--out", type=Path, help="Optional new JSON report; existing files never overwritten")
    args = parser.parse_args(argv)
    try:
        output = combine_audits(args.reports_dir, args.catalog)
        encoded = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
        print(encoded)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "audit_aggregation_failed", "reason": str(exc),
                          "training_permitted": False}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
