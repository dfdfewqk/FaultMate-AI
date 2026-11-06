"""Reconcile ORIGINAL HUST v3 MAT filenames with original paper prototype counts.

This algorithm NEVER asserts that a dataset naming code is a real independent
physical bearing or supplies new independent normal validation. It compares
exact source-SHA-verified per-file metadata to the paper's textual claim.

Primary paper: Thuan & Hong, BMC Research Notes (2023) 16:138,
https://doi.org/10.1186/s13104-023-06400-4
(27 defective prototypes and 3 healthy prototypes, 3 loads, 99 MAT signals).
Dataset: https://data.mendeley.com/datasets/cbv7jyx4p9/3 .
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

DATASET = "cbv7jyx4p9"
VERSION = 3
SOURCE_SHA_INDEX = "e6d1b9356c32383d42b4601de9e980589d887c5995a60ae3a35271289733ce42"
ORIGINAL_REPORT_SHA = "3d2d90a7998c3bdaea58e896ff2d0f95c7f72322ccb379a444d5a6e402500bcd"
AUTHOR_HEALTHY_PROTOTYPES = 3
AUTHOR_DAMAGED_PROTOTYPES = 27
EXPECTED_MAT = 99
PATTERN = re.compile(r"^(N|I|O|B|IB|IO|OB)([4-8])0([024])\.mat$")
HEX = re.compile(r"^[0-9a-f]{64}$")


class PhysicalIdentityAuditError(ValueError):
    pass


def verify_real_original_metadata(report: dict) -> dict:
    if not isinstance(report, dict):
        raise PhysicalIdentityAuditError("source_report_must_be_json_object")
    if (report.get("schema") != "faultmate_hust_hanoi_original_99_verified_research_only_v1"
        or report.get("source_id") != DATASET
        or report.get("published_version") != VERSION
        or report.get("source_index_sha256") != SOURCE_SHA_INDEX
        or report.get("real_original_mat_files_checked") != EXPECTED_MAT
        or report.get("all_original_bytes_match_first_party_file_sha256") is not True
        or report.get("all_original_mat_source_numeric_signals_parsed") is not True
        or report.get("actual_independent_healthy_physical_specimens_verified") != 0
        or report.get("actual_independent_damaged_physical_specimens_verified") != 0
        or report.get("original_stored_numeric_si_calibration_verified") is not False
        or report.get("model_activation_allowed") is not False):
        raise PhysicalIdentityAuditError("untrusted_or_promoted_original_sha_report")

    records = report.get("individual_sha256_results")
    if not isinstance(records, list) or len(records) != EXPECTED_MAT:
        raise PhysicalIdentityAuditError("complete_source_99_mat_manifest_required")
    names, hashes = set(), set()
    grouping = defaultdict(dict)
    by_fault = Counter()
    total_non_nominal = 0
    for row in records:
        if not isinstance(row, dict):
            raise PhysicalIdentityAuditError("original_mat_entry_invalid")
        name, sha, size, sample_count = (
            row.get("file"), row.get("sha256"), row.get("bytes"), row.get("sample_count"))
        match = PATTERN.fullmatch(name) if isinstance(name, str) else None
        if (match is None or name in names or not isinstance(sha, str)
            or not HEX.fullmatch(sha) or sha in hashes
            or type(size) is not int or size < 1
            or type(sample_count) is not int or sample_count < 16):
            raise PhysicalIdentityAuditError("invalid_duplicate_or_unverified_original_mat")
        names.add(name)
        hashes.add(sha)
        fault, model, load = match.groups()
        candidate_code = fault + model
        if load in grouping[candidate_code]:
            raise PhysicalIdentityAuditError("same_candidate_and_load_reused")
        grouping[candidate_code][load] = name
        by_fault[fault] += 1
        if sample_count != 512000:
            total_non_nominal += 1

    for candidate, loads in grouping.items():
        if set(loads) != {"0", "2", "4"}:
            raise PhysicalIdentityAuditError("expected_three_loads_per_filename_code:" + candidate)
    normal_codes = sorted(k for k in grouping if k.startswith("N"))
    damaged_codes = sorted(k for k in grouping if not k.startswith("N"))
    if (len(grouping) != 33 or len(normal_codes) != 5
        or len(damaged_codes) != 28 or total_non_nominal != 18
        or dict(sorted(by_fault.items())) !=
            {"B": 12, "I": 15, "IB": 12, "IO": 15, "N": 15, "O": 15, "OB": 15}):
        raise PhysicalIdentityAuditError("real_original_file_distribution_changed")
    if (report.get("observed_normal_file_naming_codes") != normal_codes
        or report.get("original_paper_reported_healthy_physical_prototypes")
            != AUTHOR_HEALTHY_PROTOTYPES
        or report.get("naming_vs_paper_healthy_specimen_count_requires_author_confirmation")
            is not True):
        raise PhysicalIdentityAuditError("source_healthy_identity_conflict_disappeared")

    return {
        "schema": "faultmate_hust_original_vs_2023_paper_physical_id_reconciliation_v1",
        "primary_dataset": "https://data.mendeley.com/datasets/cbv7jyx4p9/3",
        "primary_article": "https://doi.org/10.1186/s13104-023-06400-4",
        "official_dataset_original_sha_index": SOURCE_SHA_INDEX,
        "official_dataset_version": VERSION,
        "actual_source_sha_verified_original_mat_recordings": EXPECTED_MAT,
        "observed_original_filename_codes": len(grouping),
        "observed_normal_filename_codes": len(normal_codes),
        "observed_damaged_filename_codes": len(damaged_codes),
        "author_paper_reported_healthy_physical_prototypes": AUTHOR_HEALTHY_PROTOTYPES,
        "author_paper_reported_damaged_physical_prototypes": AUTHOR_DAMAGED_PROTOTYPES,
        "observed_naming_code_vs_author_reported_identity_mismatch": True,
        "three_load_recordings_per_filename_code": True,
        "source_mat_files_with_non_nominal_sample_lengths": total_non_nominal,
        "name_code_mappings_are_unverified_specimen_proxies": [
            {
                "filename_code_only_not_a_physical_specimen_id": candidate,
                "provisional_label_from_filename": (
                    "healthy_named" if candidate.startswith("N") else "fault_named"
                ),
                "three_load_file_names": [grouping[candidate][load] for load in ("0", "2", "4")],
                "physical_specimen_identity_author_confirmed": False,
            } for candidate in sorted(grouping)
        ],
        "verified_physical_healthy_specimen_count": 0,
        "verified_physical_damaged_specimen_count": 0,
        "new_independent_normal_evaluation_permitted": False,
        "model_training_or_retraining_performed": False,
        "historical_frozen_paderborn_classifier_compatible": False,
        "production_ml_activation_allowed": False,
        "scientific_status": "BLOCKED_UNRESOLVED_AUTHOR_PHYSICAL_SPECIMEN_MAPPING",
        "required_author_confirmation": (
            "Explain physical bearing serial identity for N400/N500/N600/N700/N800"
            " vs three healthy prototypes stated in manuscript; confirm unique "
            "specimens for the 28 faulty filename codes vs 27 manuscript prototypes;"
            " specify any re-used hardware across 3 loads and all code groups."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-source-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        path = args.official_source_report
        if path.is_symlink() or not path.is_file():
            raise PhysicalIdentityAuditError("original_source_report_missing_or_symlink")
        if args.out.exists() or args.out.is_symlink():
            raise PhysicalIdentityAuditError("refuse_overwriting_existing_research_report")
        original_bytes = path.read_bytes()
        if hashlib.sha256(original_bytes).hexdigest() != ORIGINAL_REPORT_SHA:
            raise PhysicalIdentityAuditError("original_99_file_report_sha256_mismatch")
        report = verify_real_original_metadata(json.loads(original_bytes))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as fh:
            fh.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({
            "status": report["scientific_status"],
            "originals": EXPECTED_MAT,
            "file_name_normal_groups": report["observed_normal_filename_codes"],
            "file_name_damaged_groups": report["observed_damaged_filename_codes"],
            "verified_physical_specimens": 0,
            "production_ml": False,
        }))
        return 0
    except (PhysicalIdentityAuditError, json.JSONDecodeError, OSError, ValueError) as exc:
        print("HUST_PHYSICAL_IDENTITY_NOT_VERIFIED:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
