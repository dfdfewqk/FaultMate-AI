"""Stage-4 fail-closed provenance gate for *real* Paderborn feature training.

Raw archive integrity alone does not establish that the saved sensor numbers
are calibrated in SI units. This gate checks a source-bound human review, a
complete 12-bearing raw audit and exact MAT+CSV row attestations. It does NOT
independently prove calibration or re-compute features from the original MAT.
No paid API or external network requests are made.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from faultmate.integration.ml import FEATURES
from scripts.audit_paderborn_assets import CATALOG, SourceAuditError, validate_catalog
from scripts.combine_paderborn_raw_audits import combine_audits

SOURCE_ID = "paderborn-bearing-datacenter"
LICENSE = "CC BY-NC 4.0"
SHA = re.compile(r"[a-f0-9]{64}\Z")
PRIMARY_EVIDENCE_KINDS = {"dataset_author_confirmation", "primary_dataset_documentation"}


def _json_object(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 10_000_000:
        raise ValueError("source_review_file_invalid")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("source_review_must_be_object")
    return result


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for part in iter(lambda: src.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def _row_digest(row: dict) -> str:
    """Stable digest over the actual parsed CSV values, not a file name."""
    fields = ("asset_id", "trial_id", "source_id", *FEATURES, "label", "label_provenance", "license")
    canonical = json.dumps({key: row[key] for key in fields},
                           sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_source_review(review: dict, raw_csv: bytes, summary_path: Path,
                         evidence_document: Path) -> None:
    if (review.get("dataset") != "paderborn_bearing_datacenter"
        or review.get("source_id") != SOURCE_ID or review.get("license") != LICENSE):
        raise ValueError("source_review_dataset_or_license_invalid")
    if review.get("feature_csv_sha256") != hashlib.sha256(raw_csv).hexdigest():
        raise ValueError("source_review_feature_csv_hash_mismatch")
    if review.get("raw_audit_summary_sha256") != _digest(summary_path):
        raise ValueError("source_review_raw_audit_hash_mismatch")
    if (review.get("stored_mat_numeric_units_verified") is not True
        or review.get("calibration_applies_to_whole_cohort") is not True
        or review.get("bearing_labels_verified") is not True):
        raise ValueError("source_specific_calibration_or_labels_not_reviewed")
    if review.get("actual_stored_units") != {"vibration_1": "m/s^2", "phase_current_1": "A"}:
        raise ValueError("stored_unit_mapping_not_si")
    if review.get("evidence_type") not in PRIMARY_EVIDENCE_KINDS:
        raise ValueError("primary_dataset_calibration_evidence_required")
    url = review.get("evidence_url")
    if not isinstance(url, str) or not url.startswith("https://") or len(url) <= 12:
        raise ValueError("calibration_evidence_source_url_required")
    location = review.get("evidence_location")
    if not isinstance(location, str) or len(location.strip()) < 4:
        raise ValueError("calibration_evidence_section_required")
    explanation = review.get("saved_numeric_mapping_explanation")
    if not isinstance(explanation, str) or len(explanation.strip()) < 80:
        raise ValueError("saved_mat_numeric_scaling_not_explained")
    if (evidence_document.is_symlink() or not evidence_document.is_file()
        or not 100 <= evidence_document.stat().st_size <= 20_000_000
        or evidence_document.suffix.lower() not in {".pdf", ".md", ".txt", ".eml"}):
        raise ValueError("evidence_document_missing_or_invalid")
    if review.get("evidence_document_sha256") != _digest(evidence_document):
        raise ValueError("evidence_document_sha256_mismatch")
    if (not isinstance(review.get("reviewed_by"), str)
        or len(review["reviewed_by"].strip()) < 2):
        raise ValueError("human_reviewer_missing")
    stamp = review.get("reviewed_utc")
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() != timezone.utc.utcoffset(dt):
            raise ValueError("not_utc")
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("reviewed_utc_invalid") from exc


def verify_training_readiness(
    raw_csv: bytes,
    rows: list[dict],
    *, raw_audits_dir: Path | None,
    raw_audit_summary: Path | None,
    source_review: Path | None,
    evidence_document: Path | None,
    feature_ledger: Path | None,
) -> dict:
    """Require externally verified review and exact row identities before ML.

    No automatic approval from catalog file, source MD5 or sensor model name.
    """
    if any(path is None for path in (raw_audits_dir, raw_audit_summary, source_review,
                                    evidence_document, feature_ledger)):
        raise ValueError("training_blocked_calibration_or_raw_provenance_not_supplied")
    assert raw_audits_dir is not None and raw_audit_summary is not None
    assert source_review is not None and evidence_document is not None
    assert feature_ledger is not None
    summary = _json_object(raw_audit_summary)
    recomputed = combine_audits(raw_audits_dir)
    if summary != recomputed:
        raise ValueError("raw_audit_summary_does_not_match_12_source_reports")
    if (summary.get("cohort_raw_audit_complete") is not True
        or summary.get("verified_independent_bearings") != 12
        or summary.get("inspected_recordings") != 960
        or summary.get("fully_audited_by_label") != {"healthy": 6, "damaged": 6}):
        raise ValueError("complete_12_bearing_960_recording_source_audit_required")
    review = _json_object(source_review)
    _check_source_review(review, raw_csv, raw_audit_summary, evidence_document)
    catalog = {
        item["id"]: item for item in validate_catalog(json.loads(CATALOG.read_text(encoding="utf-8")))
    }
    audit_records = {}
    duplicate_names = set()
    for path in sorted(raw_audits_dir.glob("*.json")):
        report = _json_object(path)
        bearing = report["bearing_id"]
        for record in report["recordings"]:
            key = (bearing, record["recording"])
            if key in audit_records:
                raise ValueError("repeated_recording_in_source_audit")
            audit_records[key] = record
        duplicate_names.update((bearing, d["recording"]) for d in report["duplicate_raw_recordings"])
    ledger = _json_object(feature_ledger)
    if (ledger.get("dataset") != "paderborn_bearing_datacenter"
        or ledger.get("feature_csv_sha256") != hashlib.sha256(raw_csv).hexdigest()):
        raise ValueError("feature_ledger_csv_identity_mismatch")
    entries = ledger.get("records")
    if not isinstance(entries, list) or len(entries) != len(rows):
        raise ValueError("feature_ledger_row_count_mismatch")
    indexed = {}
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("asset_id"), str) or not isinstance(item.get("trial_id"), str):
            raise ValueError("malformed_feature_ledger_record")
        key = (item["asset_id"], item["trial_id"])
        if key in indexed:
            raise ValueError("duplicate_feature_ledger_record")
        indexed[key] = item
    seen_raw = set()
    counts = Counter()
    assets_by_label = {}
    for row in rows:
        key = (row["asset_id"], row["trial_id"])
        if (row["source_id"] != SOURCE_ID or row["license"] != LICENSE
            or row["asset_id"] not in catalog
            or row["label"] != catalog[row["asset_id"]]["label"]):
            raise ValueError("training_row_source_or_bearing_label_mismatch")
        if key in duplicate_names:
            raise ValueError("duplicate_raw_recording_not_allowed_in_training")
        source = audit_records.get(key)
        assertion = indexed.get(key)
        if not source or not assertion:
            raise ValueError("training_row_not_bound_to_960_source_recordings")
        if (assertion.get("source_mat_sha256") != source["mat_sha256"]
            or assertion.get("source_raw_signal_fingerprint") != source["raw_signal_fingerprint"]
            or assertion.get("feature_row_sha256") != _row_digest(row)):
            raise ValueError("feature_row_or_raw_mat_hash_mismatch")
        fingerprint = source["raw_signal_fingerprint"]
        if fingerprint in seen_raw:
            raise ValueError("identical_raw_recording_in_training")
        seen_raw.add(fingerprint)
        name = row["asset_id"]
        if name in assets_by_label and assets_by_label[name] != row["label"]:
            raise ValueError("bearing_label_conflict")
        assets_by_label[name] = row["label"]
        counts[row["label"]] += 1
    independent = Counter(assets_by_label.values())
    if independent["healthy"] < 5 or independent["damaged"] < 5:
        raise ValueError("at_least_five_independent_bearings_per_class_required")
    return {
        "source_verified": True, "cohort_raw_audit_complete": True,
        "human_calibration_review_present": True,
        "independent_bearings": dict(independent),
        "source_recordings_selected": len(rows),
        "source_audit_sha256": _digest(raw_audit_summary),
        "review_sha256": _digest(source_review),
        "feature_ledger_sha256": _digest(feature_ledger),
        "warning": "Review evidence is human-attested; the code cannot independently prove physical calibration.",
    }
