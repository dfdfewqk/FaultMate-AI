"""Inspect ACTUAL new original-file bytes before any future bearing ML experiment.

This is a file-identity and modality preflight, not proof of physical specimen
identity, author-authenticated health labels, SI calibration, or model validity.
No network, model scoring, training, CSV-model activation, or overwrite occurs.

HUST 2023 is independently published but VIBRATION-ONLY and has a different
sampling and load protocol. It may be studied in an entirely separate model;
it MUST NEVER be passed to the frozen Paderborn vibration+current classifier.

All six Paderborn healthy physical bearings were previously opened; they
cannot become new independent normal specimens by splitting measurements.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_independent_bearing_preflight import EXPOSED_PADERBORN

SCHEMA = "faultmate_external_original_bearing_file_intake_v1"
SOURCES = {
    "hust_bearing_v3": {
        "primary_dataset_url": "https://data.mendeley.com/datasets/cbv7jyx4p9/3",
        "primary_publication_url": "https://doi.org/10.1186/s13104-023-06400-4",
        "license": "CC BY 4.0",
        "vibration_hz": 51200,
        "motor_current_hz": None,
        "condition_count": 3,
        "paired_vibration_and_motor_current": False,
        "paderborn_6203_four_conditions_compatible": False,
        "original_healthy_physical_specimens_reported": 3,
        "new_dataset_published": True,
    },
    "paderborn_2016": {
        "primary_dataset_url": "https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download",
        "primary_publication_url": "https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter",
        "license": "CC BY-NC 4.0",
        "vibration_hz": 64000,
        "motor_current_hz": 64000,
        "condition_count": 4,
        "paired_vibration_and_motor_current": True,
        "paderborn_6203_four_conditions_compatible": True,
        "original_healthy_physical_specimens_reported": 6,
        "new_dataset_published": False,
    },
}
SHA = re.compile(r"^[0-9a-f]{64}$")
ID = re.compile(r"^[a-zA-Z0-9_:-]{2,80}$")
PERMITTED_EXT = {".mat", ".rar", ".csv", ".zip"}


class IntakeError(ValueError):
    pass


def _within_original_root(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise IntakeError("original_relative_path_invalid")
    p = PurePosixPath(relative)
    if (p.is_absolute() or ".." in p.parts or "." in p.parts
        or len(p.parts) > 8 or p.suffix.lower() not in PERMITTED_EXT):
        raise IntakeError("original_relative_path_invalid")
    target = root
    for part in p.parts:
        target = target / part
        if target.is_symlink():
            raise IntakeError("source_path_symlink_forbidden")
    if not target.is_file():
        raise IntakeError("original_file_missing")
    if not target.resolve().is_relative_to(root.resolve()):
        raise IntakeError("original_path_outside_source_root")
    return target


def _sha256_original(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def inspect_source(original_root: Path, manifest: dict) -> dict:
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise IntakeError("external_source_manifest_schema_invalid")
    if manifest.get("status") != "candidate_not_author_verified":
        raise IntakeError("unapproved_source_cannot_claim_author_verification")
    key = manifest.get("source_id")
    source = SOURCES.get(key)
    if source is None:
        raise IntakeError("unknown_external_dataset_no_author_registry")
    if (manifest.get("primary_dataset_url") != source["primary_dataset_url"]
        or manifest.get("license") != source["license"]):
        raise IntakeError("source_identity_or_license_mismatch")
    if manifest.get("source_numeric_si_calibration_verified") is not False:
        raise IntakeError("unverified_si_calibration_cannot_be_claimed")
    if manifest.get("physical_label_provenance_author_verified") is not False:
        raise IntakeError("unverified_physical_labels_cannot_be_claimed")
    if manifest.get("automatically_activate_runtime_model") is not False:
        raise IntakeError("model_activation_forbidden")
    groups = manifest.get("proposed_specimens")
    if not isinstance(groups, list) or len(groups) > 200:
        raise IntakeError("original_specimen_list_invalid")
    if not original_root.is_dir() or original_root.is_symlink():
        raise IntakeError("original_source_root_missing_or_symlink")
    identifiers: set[str] = set()
    filepaths: set[str] = set()
    hashes: set[str] = set()
    rows = []
    for group in groups:
        if not isinstance(group, dict):
            raise IntakeError("invalid_physical_specimen_claim")
        physical_id = group.get("claimed_physical_specimen_id")
        label = group.get("claimed_original_label")
        if (not isinstance(physical_id, str) or not ID.fullmatch(physical_id)
            or physical_id in identifiers or physical_id in EXPOSED_PADERBORN
            or label not in ("healthy", "damaged")):
            raise IntakeError("physical_specimen_id_reused_or_invalid")
        identifiers.add(physical_id)
        files = group.get("files")
        if not isinstance(files, list) or not 1 <= len(files) <= 120:
            raise IntakeError("physical_specimen_original_files_required")
        file_checks = []
        for item in files:
            if not isinstance(item, dict):
                raise IntakeError("file_identity_record_invalid")
            rel, expected = item.get("relative_path"), item.get("sha256")
            if not isinstance(expected, str) or not SHA.fullmatch(expected):
                raise IntakeError("pinned_original_file_sha256_required")
            # Both duplicate filenames and duplicate bytes cross any claimed
            # physical group mean identity/independence is not established.
            if rel in filepaths or expected in hashes:
                raise IntakeError("duplicate_source_file_or_raw_sha256")
            target = _within_original_root(original_root, rel)
            actual = _sha256_original(target)
            if actual != expected:
                raise IntakeError("original_source_file_sha256_mismatch")
            filepaths.add(rel)
            hashes.add(actual)
            file_checks.append({"relative_path": rel, "original_sha256": actual,
                                "original_bytes_verified": True})
        rows.append({"claimed_physical_specimen_id": physical_id,
                     "claimed_original_label": label, "files": file_checks,
                     "author_physical_identity_and_label_verified": False})
    return {
        "schema": "faultmate_external_original_bearing_intake_result_v1",
        "status": "ORIGINAL_BYTES_VERIFIED_RESEARCH_ONLY"
                  if rows else "NO_NEW_ORIGINAL_BYTES_SUPPLIED",
        "source_id": key,
        "primary_source_url": source["primary_dataset_url"],
        "primary_publication_url": source["primary_publication_url"],
        "license_as_published": source["license"],
        "publisher_reported_normal_specimens_not_individually_verified_here":
            source["original_healthy_physical_specimens_reported"],
        "verified_original_file_count": len(filepaths),
        "claimed_physical_specimen_count": len(rows),
        "claimed_healthy_specimens": sum(x["claimed_original_label"] == "healthy" for x in rows),
        "claimed_damaged_specimens": sum(x["claimed_original_label"] == "damaged" for x in rows),
        "verified_source_bytes": bool(rows),
        "source_protocol": {
            k: source[k] for k in ("vibration_hz", "motor_current_hz",
                "condition_count", "paired_vibration_and_motor_current",
                "paderborn_6203_four_conditions_compatible")
        },
        "compatibility_with_existing_paderborn_12_feature_model": (
            "INPUT_PROTOCOL_ONLY_SOURCE_MATCH_NOT_FRESH_NORMAL_DATA"
            if key == "paderborn_2016"
            else "INCOMPATIBLE_NEW_DOMAIN_REQUIRES_SEPARATE_MODEL"),
        "original_source_file_evidence": rows,
        "physical_identity_and_health_labels_independently_verified": False,
        "signal_channels_and_numeric_si_units_verified": False,
        "new_prospective_independent_normal_test_passed": False,
        "normal_false_alarm_rate_and_specificity_measured": False,
        "frozen_paderborn_model_scoring_allowed": False,
        "separate_new_domain_model_training_approved": False,
        "production_ml_activation_allowed": False,
        "model_changed_or_trained": False,
        "paid_deepseek_api_called": False,
        "notice": (
            "원본 파일 바이트 일치 여부만 확인했습니다. 출처 저자의 물리 개체 ID·"
            "정상/손상 라벨 및 센서 수치 단위는 검증되지 않았습니다. "
            "HUST는 별도 진동 전용 모델 연구가 필요하며 Paderborn 모델에 연결할 수 없습니다."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--original-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if args.manifest.is_symlink() or not args.manifest.is_file():
            raise IntakeError("intake_manifest_missing_or_symlink")
        if args.manifest.stat().st_size > 256_000:
            raise IntakeError("intake_manifest_too_large")
        m = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = inspect_source(args.original_root, m)
        if args.out is not None:
            if args.out.exists() or args.out.is_symlink():
                raise IntakeError("refuse_overwrite_prior_original_source_report")
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as output:
                output.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({
            "status": report["status"], "source_id": report["source_id"],
            "verified_original_file_count": report["verified_original_file_count"],
            "new_independent_validation": False, "production_ml_activation": False,
        }, ensure_ascii=False))
        return 0
    except (ValueError, OSError, UnicodeError, TypeError, KeyError) as exc:
        print("ORIGINAL_SOURCE_INTAKE_BLOCKED:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
