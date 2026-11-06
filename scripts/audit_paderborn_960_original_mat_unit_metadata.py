"""Evidence-based audit of original Paderborn MAT channel Unit metadata (12 bearings).

Only source-verifiable original-derived metadata saved by the PREVIOUSLY
successful 960-MAT audit are read. Their per-file SHA256 must match the pinned
original study. This is a count of observed MAT Unit entries, NOT SI calibration
and does not activate any model, write CSV, download RAR, or call DeepSeek.

Primary physical transducer models / nominal sampling come from Lessmeier et
al. 2016. The paper does not specify how Y.Data MATLAB numeric values were
scaled or offset for publication. Do not convert sensor gain specs to SI.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_paderborn_assets import (
    CATALOG, SourceAuditError, validate_catalog,
)

BASELINE_SHA = "f52fb71ec166d056ccad610cbbe991660c63ab98e147a7e45147f0e802a6452c"
ORIGINAL_STUDY_RUN = 41965647928
RAW_MAT_AUDIT_RUN = 41957475830
SHA = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise SourceAuditError("original_source_evidence_missing_or_symlink")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_one_original_report(report: dict, bearing_id: str, expected: dict) -> dict:
    if (not isinstance(report, dict)
        or report.get("bearing_id") != bearing_id
        or report.get("label") != expected["label"]
        or report.get("source_md5_verified") is not True
        or report.get("source_archive_md5") != expected["md5"]
        or report.get("raw_units_verified") is not False
        or report.get("si_csv_generated") is not False
        or report.get("ml_trained") is not False
        or report.get("model_activated") is not False
        or report.get("approved_for_training") is not False
        or report.get("inspected_recordings") != 80):
        raise SourceAuditError("original_raw_mat_metadata_status_invalid:" + bearing_id)

    records = report.get("recordings")
    if not isinstance(records, list) or len(records) != 80:
        raise SourceAuditError("original_mat_record_count_invalid:" + bearing_id)
    names = set()
    mat_hashes = set()
    unit_pairs = Counter()
    for record in records:
        if not isinstance(record, dict):
            raise SourceAuditError("original_mat_metadata_record_invalid:" + bearing_id)
        name = record.get("recording")
        namepattern = rf"^N\d{{2}}_M\d{{2}}_F\d{{2}}_{re.escape(bearing_id)}_(?:[1-9]|1\d|20)\.mat$"
        mat_sha = record.get("mat_sha256")
        fp = record.get("raw_signal_fingerprint")
        if (not isinstance(name, str) or re.fullmatch(namepattern, name) is None
            or name in names or not isinstance(mat_sha, str)
            or SHA.fullmatch(mat_sha) is None
            or mat_sha in mat_hashes or not isinstance(fp, str)
            or SHA.fullmatch(fp) is None
            or type(record.get("sample_count")) is not int
            or record["sample_count"] < 16
            or record.get("vibration_channel") != "vibration_1"
            or record.get("current_channel") != "phase_current_1"):
            raise SourceAuditError("original_mat_record_source_invalid:" + bearing_id)
        names.add(name)
        mat_hashes.add(mat_sha)
        vib = record.get("raw_vibration_unit")
        curr = record.get("raw_current_unit")
        if (not isinstance(vib, str) or not vib
            or not isinstance(curr, str) or not curr):
            raise SourceAuditError("raw_mat_unit_entry_missing:" + bearing_id)
        for key in ("raw_rms_vibration_unscaled",
                    "raw_peak_abs_vibration_unscaled",
                    "raw_rms_current_unscaled"):
            value = record.get(key)
            if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
                raise SourceAuditError("invalid_raw_unscaled_signal_summary:" + bearing_id)
        unit_pairs[(vib, curr)] += 1
    return {
        "bearing_id": bearing_id,
        "source_mat_records": 80,
        "original_mat_unit_pair_counts": [
            {"vibration_mat_unit": pair[0],
             "phase_current_mat_unit": pair[1],
             "original_mat_files": count}
            for pair, count in sorted(unit_pairs.items())
        ],
        "both_mat_unit_entries_unknown": unit_pairs.get(("unknown", "unknown"), 0),
        "publisher_sha_verified_original_mat_count": len(mat_hashes),
        "author_data_scale_and_offset_confirmed": False,
    }


def audit_all_original_metadata(audit_folder: Path, baseline_file: Path):
    if sha256_file(baseline_file) != BASELINE_SHA:
        raise SourceAuditError("original_research_evaluation_SHA_mismatch")
    baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
    provenance = baseline.get("provenance")
    if (baseline.get("ml_model_approved") is not False
        or not isinstance(provenance, dict)
        or provenance.get("source_bearings") != 12
        or provenance.get("source_recordings") != 960
        or provenance.get("unique_recordings") != 956
        or provenance.get("physical_si_units_verified") is not False):
        raise SourceAuditError("original_research_baseline_provenance_invalid")
    manifest = provenance.get("source_audit_sha256")
    if not isinstance(manifest, list) or len(manifest) != 12:
        raise SourceAuditError("baseline_original_per_bearing_manifest_missing")
    expected = {x["id"]: x for x in validate_catalog(
        json.loads(CATALOG.read_text(encoding="utf-8")))}
    by_bearing = {x.get("bearing_id"): x for x in manifest if isinstance(x, dict)}
    if len(by_bearing) != 12 or set(by_bearing) != set(expected):
        raise SourceAuditError("baseline_original_bearing_manifest_invalid")
    if (not audit_folder.is_dir() or audit_folder.is_symlink()
        or sorted(p.name for p in audit_folder.glob("*.json")) !=
        sorted(f"{k}.json" for k in expected)):
        raise SourceAuditError("require_all_12_prior_original_mat_audit_json")

    units = Counter()
    reports = []
    for bearing, catalog_entry in sorted(expected.items()):
        f = audit_folder / f"{bearing}.json"
        if sha256_file(f) != by_bearing[bearing].get("raw_audit_sha256"):
            raise SourceAuditError("original_mat_source_audit_sha_changed:" + bearing)
        individual = audit_one_original_report(
            json.loads(f.read_text(encoding="utf-8")), bearing, catalog_entry)
        reports.append(individual)
        for item in individual["original_mat_unit_pair_counts"]:
            units[(item["vibration_mat_unit"], item["phase_current_mat_unit"])] += (
                item["original_mat_files"])
    if sum(units.values()) != 960:
        raise SourceAuditError("all_960_mat_unit_entries_required")
    return {
        "schema": "faultmate_paderborn_original_960_mat_stored_unit_evidence_v1",
        "status": "ORIGINAL_MAT_UNIT_ENTRIES_AUDITED_SI_UNRESOLVED",
        "original_study_sha256": BASELINE_SHA,
        "original_study_run": ORIGINAL_STUDY_RUN,
        "raw_original_mat_audit_run": RAW_MAT_AUDIT_RUN,
        "source_recordings": 960,
        "original_physical_bearings": 12,
        "independent_new_physical_bearings_tested": 0,
        "unique_original_raw_signals": 956,
        "actual_prior_raw_audits_sha_verification": True,
        "observed_mat_unit_pair_counts": [
            {"vibration_mat_unit": a, "phase_current_mat_unit": b,
             "source_mat_files": count} for (a, b), count in sorted(units.items())
        ],
        "both_mat_units_unknown_count": units.get(("unknown", "unknown"), 0),
        "all_mat_units_explicitly_si": False,
        "paper_reports_physical_measurands": (
            "motor phase current measured by LEM CKSR 15-NP; "
            "housing acceleration by PCB 336C04 + Kistler 5015A; "
            "nominal ADC sample rate 64000/s"
        ),
        "paper_proves_stored_mat_numeric_values_are_si": False,
        "author_supplied_numeric_to_si_factors_offsets": False,
        "author_original_calibration_document_secured": False,
        "physical_sensor_values_converted_to_si": False,
        "si_csv_generated": False,
        "model_retrained_or_activated": False,
        "production_ml_activation_allowed": False,
        "individual_bearing_unit_fields": reports,
        "needed_primary_evidence": [
            "dataset-specific stored vibration_1.Y.Data physical unit/scale and offset",
            "dataset-specific stored phase_current_1.Y.Data physical unit/scale and DC offset",
            "confirmation whether analog gain and amplifier sensitivity already applied",
            "scope of the calibration across all 32 bearings and four conditions",
        ],
        "notice": (
            "검사된 원본 MAT의 Unit 값과 원저자의 실제 저장 수치 단위는 구분해야 합니다."
            " 원 논문은 센서 종류/측정량만 설명하고 MATLAB Y.Data의 저장 수치 변환을"
            " 명시하지 않습니다. 확인되지 않은 감도와 오프셋을 임의로 보정하지 않았습니다."
        ),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-audits", type=Path, required=True)
    p.add_argument("--original-evaluation", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.out.exists() or args.out.is_symlink():
            raise SourceAuditError("refuse_overwrite_previous_unit_report")
        data = audit_all_original_metadata(args.raw_audits, args.original_evaluation)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as fh:
            fh.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({
            "status": data["status"],
            "source_mat_recordings": data["source_recordings"],
            "unknown_raw_mat_unit_pairs": data["both_mat_units_unknown_count"],
            "si_numeric_calibration_verified": False,
            "production_model_approved": False,
        }))
        return 0
    except (SourceAuditError, OSError, KeyError, ValueError, TypeError) as exc:
        print("PADERBORN_RAW_SI_SOURCE_VERIFICATION_BLOCKED:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
