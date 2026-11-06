"""Verify all 99 HUST Hanoi v3 ORIGINAL MAT bytes against publisher SHA256.

Runs in five bounded shards with NO raw signal artifacts. This is genuine
public dataset source intake, not a trained model, new blind independent
external validation, or SI physical calibration. The paper describes 3
healthy prototypes, while the published names may contain five distinct
N4..N8 codes. Names are NOT authenticated independent physical IDs.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
from collections import Counter
import sys

# Direct Windows/Linux CLI invocation must resolve the repository package root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_hust_official_public_original import (
    DATASET, VERSION, _get_url, published_files, MAX_SIGNAL, PublicSourceError,
)

SCHEMA = "faultmate_hust_hanoi_2023_original_99_first_party_sha_verification_v1"
NAME = re.compile(r"^(?P<fault>N|I|O|B|IB|IO|OB)(?P<type>[4-8])0(?P<load>[024])\.mat$")
SHARDS = 5
ORIGINALS = 99


def official_mat_index():
    entries = sorted((x for x in published_files()
                      if x["name"].lower().endswith(".mat")), key=lambda x: x["name"])
    if len(entries) != ORIGINALS:
        raise PublicSourceError("published_original_mat_count_not_99")
    names, hashes = set(), set()
    for entry in entries:
        name = entry["name"]
        if not NAME.fullmatch(name):
            raise PublicSourceError("publisher_file_name_outside_original_2023_paper_contract:" + name)
        if name in names or entry["sha256"] in hashes:
            raise PublicSourceError("publisher_duplicate_name_or_source_sha")
        names.add(name)
        hashes.add(entry["sha256"])
        if entry["size"] > MAX_SIGNAL:
            raise PublicSourceError("original_file_exceeds_safe_per_file_size")
    index_without_ephemeral_urls = [
        [x["name"], x["sha256"], x["size"], x["folder"]] for x in entries
    ]
    sha = hashlib.sha256(json.dumps(
        index_without_ephemeral_urls, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return entries, sha


def verify_shard(shard: int, shard_count: int, downloader=_get_url):
    if type(shard) is not int or not 0 <= shard < shard_count or shard_count != SHARDS:
        raise PublicSourceError("invalid_original_audit_shard")
    entries, index_sha = official_mat_index()
    subset = [x for i, x in enumerate(entries) if i % shard_count == shard]
    # Summary jobs are stdlib-only; original signal parsing needs SciPy only
    # on the actual SHA-verification shards, not during report aggregation.
    import numpy as np
    from scipy.io import loadmat

    records = []
    for entry in subset:
        raw = downloader(entry["download_url"], MAX_SIGNAL)
        if len(raw) != entry["size"]:
            raise PublicSourceError("source_original_byte_count_changed:" + entry["name"])
        actual = hashlib.sha256(raw).hexdigest()
        if actual != entry["sha256"]:
            raise PublicSourceError("source_original_sha_does_not_match_publisher:" + entry["name"])
        try:
            doc = loadmat(io.BytesIO(raw), squeeze_me=True)
            wave = np.asarray(doc["data"])
            # The publication describes nominal 10s x 51.2kHz, but actual
            # original recording lengths may differ. Verify and REPORT each
            # original length rather than fabricating samples or silently
            # deleting valid publisher-checksummed files from the cohort.
            if (wave.size < 16 or not np.issubdtype(wave.dtype, np.number)
                    or np.iscomplexobj(wave) or not np.isfinite(wave).all()):
                raise PublicSourceError(
                    "source_original_numeric_vibration_invalid:" +
                    entry["name"] + ":samples=" + str(wave.size))
        except PublicSourceError:
            raise
        except (KeyError, TypeError, ValueError, NotImplementedError) as exc:
            raise PublicSourceError("source_original_mat_unreadable:" + entry["name"]) from exc
        m = NAME.fullmatch(entry["name"])
        records.append({
            "original_name": entry["name"],
            "publisher_sha256": entry["sha256"],
            "actual_bytes_sha256": actual,
            "publisher_byte_count": entry["size"],
            "actual_byte_count": len(raw),
            "observed_vibration_samples": int(wave.size),
            "matches_published_nominal_10sec_51200hz": bool(wave.size == 512000),
            "file_name_fault_code": m["fault"],
            "file_name_bearing_type_code": m["type"],
            "file_name_load_code": m["load"],
            "publisher_sha_and_actual_bytes_match": True,
        })
    return {
        "schema": SCHEMA, "source_id": DATASET, "source_version": VERSION,
        "original_count_in_first_party_index": ORIGINALS,
        "first_party_index_sha256": index_sha,
        "shard_index": shard, "shard_count": shard_count,
        "actual_original_mat_files_verified": len(records),
        "records": records,
        "original_raw_signals_stored_in_artifacts": False,
        "original_file_names_are_physical_identity_proof": False,
        "numerical_signal_si_calibration_verified": False,
        "previously_frozen_paderborn_model_compatible": False,
        "new_independent_normal_model_validation": False,
        "production_ml_approved": False,
    }


def merge_shards(folder: Path):
    paths = sorted(folder.glob("shard-*.json"))
    if len(paths) != SHARDS:
        raise PublicSourceError("not_all_five_source_shards_present")
    reports = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    if (any(r.get("schema") != SCHEMA or r.get("source_id") != DATASET
            or r.get("source_version") != VERSION or r.get("shard_count") != SHARDS
            or r.get("original_count_in_first_party_index") != ORIGINALS
            or r.get("production_ml_approved") is not False
            or r.get("original_raw_signals_stored_in_artifacts") is not False
            for r in reports)
        or sorted(r["shard_index"] for r in reports) != list(range(SHARDS))
        or len({r["first_party_index_sha256"] for r in reports}) != 1):
        raise PublicSourceError("publisher_original_shard_evidence_mismatch")
    records = [row for report in reports for row in report["records"]]
    names = [r["original_name"] for r in records]
    hashes = [r["actual_bytes_sha256"] for r in records]
    if (len(records) != ORIGINALS or len(set(names)) != ORIGINALS
        or len(set(hashes)) != ORIGINALS
        or any(r["publisher_sha_and_actual_bytes_match"] is not True
               or r["publisher_sha256"] != r["actual_bytes_sha256"]
               or r["publisher_byte_count"] != r["actual_byte_count"]
               or r["observed_vibration_samples"] < 16
               or NAME.fullmatch(r["original_name"]) is None
               for r in records)):
        raise PublicSourceError("source_shards_incomplete_or_corrupt")
    fault_counts = Counter(r["file_name_fault_code"] for r in records)
    normal_names = sorted(r["original_name"] for r in records if r["file_name_fault_code"] == "N")
    normal_codes = sorted({r["file_name_fault_code"] +
                           r["file_name_bearing_type_code"]
                           for r in records if r["file_name_fault_code"] == "N"})
    if len(normal_names) != 15 or len(normal_codes) != 5:
        raise PublicSourceError("publisher_normal_file_naming_unexpected")
    return {
        "schema": "faultmate_hust_hanoi_original_99_verified_research_only_v1",
        "source_id": DATASET,
        "published_version": VERSION,
        "source_index_sha256": reports[0]["first_party_index_sha256"],
        "real_original_mat_files_checked": ORIGINALS,
        "all_original_bytes_match_first_party_file_sha256": True,
        "all_original_mat_source_numeric_signals_parsed": True,
        "observed_file_name_fault_code_counts": dict(sorted(fault_counts.items())),
        "observed_normal_file_names": normal_names,
        "observed_normal_file_naming_codes": normal_codes,
        "observed_normal_code_count": len(normal_codes),
        "originals_with_nominal_512000_samples": sum(
            r["observed_vibration_samples"] == 512000 for r in records),
        "originals_with_other_recording_lengths": [
            {"file": r["original_name"], "sample_count": r["observed_vibration_samples"]}
            for r in records if r["observed_vibration_samples"] != 512000
        ],
        "original_paper_reported_healthy_physical_prototypes": 3,
        "naming_vs_paper_healthy_specimen_count_requires_author_confirmation":
            len(normal_codes) != 3,
        "actual_independent_healthy_physical_specimens_verified": 0,
        "actual_independent_damaged_physical_specimens_verified": 0,
        "original_stored_numeric_si_calibration_verified": False,
        "fixed_paderborn_12_feature_vibration_current_model_compatible": False,
        "new_independent_generalization_validated": False,
        "new_model_trained_or_approved": False,
        "model_activation_allowed": False,
        "source_original_raw_data_preserved_outside_artifacts": True,
        "individual_sha256_results": [
            {"file": r["original_name"], "sha256": r["actual_bytes_sha256"],
             "bytes": r["actual_byte_count"],
             "sample_count": r["observed_vibration_samples"]}
            for r in sorted(records, key=lambda r: r["original_name"])
        ],
        "warning": (
            "99개 원본 MAT의 진동 신호와 공식 SHA256이 확인돼도,"
            " 파일명상 N4..N8 5개 코드와 논문 정상 시제품 3개 표기는 다릅니다."
            " 파일명은 독립 물리베어링 신원 증명이 아니며,"
            " 신규 검증/범용 생산용 ML 승인은 금지됩니다."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--shard", type=int)
    group.add_argument("--merge-dir", type=Path)
    parser.add_argument("--shards", type=int, default=SHARDS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.out.exists() or args.out.is_symlink():
            raise PublicSourceError("refuse_overwrite_prior_original_sha_report")
        report = (merge_shards(args.merge_dir)
                  if args.merge_dir is not None
                  else verify_shard(args.shard, args.shards))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(json.dumps({
            "status": "ORIGINAL_SHA_VERIFIED_RESEARCH_ONLY",
            "actual_mat_files_verified": report.get(
                "actual_original_mat_files_verified",
                report.get("real_original_mat_files_checked", 0)),
            "production_model_active": False,
            "source_si_verified": False,
            "new_independent_normal_validation": False,
        }))
        return 0
    except (PublicSourceError, OSError, ValueError, TypeError, KeyError) as exc:
        print("HUST_OFFICIAL_ORIGINAL_99_AUDIT_BLOCKED:", str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
