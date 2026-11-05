"""OFFLINE research-only inference: original Paderborn RAR -> 80 MAT -> ML.

Reuses the original MD5/integrity/channel/extraction code and the *exact*
already-frozen 12-feature aggregated logistic model. NEVER trains or edits the
model, produces a field-usable diagnosis, calls DeepSeek, or changes the
existing production /api/ml/inspect path (which must remain unavailable).

This script accepts only one original catalogued 100MB+ RAR with matching
source MD5; raw sensor MATs exist only in the extractor's temporary folder.
The output report is intentionally short, never raw signals or 80 features.

Usage:
    python scripts/run_experimental_paderborn_ml.py \
      --archive /some/existing/K001.rar --bearing-id K001 \
      --out /some/NEW/report.json
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import re
import shutil
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_paderborn_assets import (
    CATALOG, OFFICIAL_CONDITIONS, SourceAuditError, validate_catalog,
)
from scripts.extract_paderborn_unitless import (
    FEATURE_NAMES, SCHEMA, extract_archive,
)
from scripts.evaluate_unseen_paderborn_damaged import frozen_coefficients

SHA_64 = re.compile(r"[0-9a-f]{64}\Z")
SCHEMA_RESULT = "faultmate_research_paderborn_real_archive_ml_v1"


def aggregate_verified_feature_report(doc: dict) -> tuple[np.ndarray, dict]:
    """Check FULL 4×20 research features before forming one bearing vector.

    A JSON object, even if valid, does not authenticate an original archive.
    For such authentication ONLY run_archive() can call extract_archive() after
    checking the actual raw archive MD5. This function NEVER trusts strings
    like archive_verified as evidence of physical origin by themselves.
    """
    if not isinstance(doc, dict):
        raise SourceAuditError("research_feature_report_object_required")
    catalog = {
        row["id"]: row for row in validate_catalog(
            json.loads(CATALOG.read_text(encoding="utf-8")))
    }
    asset = doc.get("bearing_id")
    source = catalog.get(asset)
    if source is None:
        raise SourceAuditError("research_bearing_not_in_original_12_catalog")
    if (
        doc.get("schema") != SCHEMA
        or doc.get("status") != "real_raw_unitless_features_unreviewed"
        or doc.get("dataset") != "paderborn_bearing_datacenter"
        or doc.get("label") != source["label"]
        or doc.get("official_archive_md5") != source["md5"]
        or doc.get("license") != "CC BY-NC 4.0"
        or doc.get("archive_verified") is not True
        or doc.get("raw_si_units_verified") is not False
        or doc.get("si_amplitudes_used") is not False
        or doc.get("ml_trained") is not False
        or doc.get("approved_for_runtime") is not False
        or list(doc.get("feature_names", [])) != list(FEATURE_NAMES)
        or doc.get("source_recording_count") != 80
    ):
        raise SourceAuditError("research_original_feature_contract_invalid")
    rows = doc.get("records")
    if not isinstance(rows, list) or len(rows) != 80:
        raise SourceAuditError("research_requires_all_80_original_records")

    seen_names: set[str] = set()
    first_fp: dict[str, str] = {}
    duplicate_rows: list[dict] = []
    conditions: dict[str, set[int]] = defaultdict(set)
    unique_values: list[list[float]] = []

    for r in rows:
        if not isinstance(r, dict):
            raise SourceAuditError("research_record_not_an_object")
        cond, trial, recording = r.get("condition"), r.get("trial"), r.get("recording")
        if (
            cond not in OFFICIAL_CONDITIONS or
            type(trial) is not int or not 1 <= trial <= 20 or
            recording != f"{cond}_{asset}_{trial}.mat" or
            recording in seen_names
        ):
            raise SourceAuditError("research_original_condition_trial_invalid")
        seen_names.add(recording)
        conditions[cond].add(trial)
        sha = r.get("source_mat_sha256")
        fp = r.get("source_raw_signal_fingerprint")
        if (
            not isinstance(sha, str) or SHA_64.fullmatch(sha) is None
            or not isinstance(fp, str) or SHA_64.fullmatch(fp) is None
            or type(r.get("sample_count")) is not int
            or r["sample_count"] < 16384
        ):
            raise SourceAuditError("research_missing_raw_signal_fingerprint")
        previous = first_fp.get(fp)
        if r.get("duplicate_of") != previous:
            raise SourceAuditError("research_duplicate_recording_mismatch")
        if previous:
            if r.get("values") is not None:
                raise SourceAuditError("research_duplicate_signal_was_scored")
            duplicate_rows.append({"recording": recording, "duplicate_of": previous})
        else:
            first_fp[fp] = recording
            values = r.get("values")
            if (
                not isinstance(values, list)
                or len(values) != len(FEATURE_NAMES)
                or any(
                    type(x) not in (float, int) or not math.isfinite(x)
                    for x in values
                )
            ):
                raise SourceAuditError("research_dimensionless_feature_invalid")
            unique_values.append([float(x) for x in values])
    if (
        set(conditions) != OFFICIAL_CONDITIONS or
        any(trials != set(range(1, 21)) for trials in conditions.values())
    ):
        raise SourceAuditError("research_incomplete_four_conditions")
    if (
        doc.get("duplicates") != duplicate_rows
        or doc.get("unique_recording_count") != len(unique_values)
        or len(unique_values) < 60
        or len(unique_values) + len(duplicate_rows) != 80
    ):
        raise SourceAuditError("research_duplicate_summary_inconsistent")
    median = np.median(np.asarray(unique_values, dtype=np.float64), axis=0)
    if median.shape != (len(FEATURE_NAMES),) or not np.all(np.isfinite(median)):
        raise SourceAuditError("research_invalid_aggregated_feature_vector")
    return median, {
        "bearing_id": asset,
        "label_from_original_catalog": source["label"],
        "source_records": 80,
        "unique_signal_pairs": len(unique_values),
        "duplicates_excluded": len(duplicate_rows),
        "four_source_conditions_present": True,
    }


def score_original_feature_report(doc: dict) -> dict:
    """Research score on declared data, NOT physical provenance verification.

    The real RAR -> MAT -> verified original input path is run_archive() below.
    Tests can use this function with synthetic feature reports; no simulated
    input is ever counted as a new measured result or accuracy claim.
    """
    aggregated, source = aggregate_verified_feature_report(doc)
    model = frozen_coefficients()  # Original pinned JSON SHA and no-approval contract
    # This matches the *previously frozen* one-time unseen-damaged evaluator.
    z = (aggregated - model["mean"]) / model["scale"]
    logit = float(np.dot(z, model["coefs"]) + model["intercept"])
    if not math.isfinite(logit):
        raise SourceAuditError("research_model_invalid_logit")
    if logit >= 0:
        score = 1.0 / (1.0 + math.exp(-logit))
    else:
        e = math.exp(logit)
        score = e / (1.0 + e)
    if not 0 <= score <= 1:
        raise SourceAuditError("research_model_invalid_score")
    predicted = "damaged" if score >= model["threshold"] else "healthy"
    return {
        "schema": SCHEMA_RESULT,
        "status": "experimental_model_scored_unapproved_not_for_field_use",
        "research_input_source": source,
        "research_feature_schema": SCHEMA,
        "frozen_model_sha256": model["model_sha256"],
        "frozen_threshold": model["threshold"],
        "experimental_damage_model_score": round(float(score), 8),
        "experimental_predicted_label": predicted,
        "feature_computation": "real_raw_unitless_12_feature_bearing_median_4x20",
        "raw_signal_physical_SI_units_verified": False,
        "independent_heldout_healthy_specificity_measured": False,
        "result_may_include_previously_trained_bearing": True,
        "model_refitting_or_threshold_tuning_performed": False,
        "runtime_ml_model_approved": False,
        "confirmed_fault": False,
        "safe_to_work": False,
        "experimental_research_only": True,
        "license": "CC BY-NC 4.0",
    }


def run_archive(archive: Path, bearing_id: str, *, sevenzip: str) -> dict:
    """Actual source MD5, archive test, 80 original MAT channels, features, ML."""
    bearing_id = bearing_id.upper()
    report = extract_archive(
        archive.absolute(), bearing_id, sevenzip=sevenzip,
    )
    result = score_original_feature_report(report)
    # Only THIS function establishes real original RAR evidence, because it
    # directly invoked extract_archive's actual source-MD5 and 80-MAT checks.
    result["source_archive_verified_from_original_bytes_same_run"] = True
    result["source_mat_files_actually_read_this_run"] = 80
    result["new_independent_test_bearing_claimed"] = False
    result["is_validated_field_accuracy"] = False
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--bearing-id", required=True)
    parser.add_argument("--sevenzip", help="Existing 7z executable")
    parser.add_argument("--out", type=Path, required=True,
                        help="NEW JSON report path. Never overwrite.")
    args = parser.parse_args(argv)
    try:
        sevenzip = args.sevenzip or shutil.which("7z") or shutil.which("7zz")
        if not sevenzip and sys.platform == "win32":
            candidate = Path(r"C:\Program Files\7-Zip\7z.exe")
            sevenzip = str(candidate) if candidate.is_file() else None
        if not sevenzip:
            raise SourceAuditError("sevenzip_unavailable")
        if args.out.exists() or args.out.is_symlink():
            raise SourceAuditError("research_result_already_exists_no_overwrite")
        # Do NOT create any output unless raw original extraction AND actual
        # model scoring both complete. Existing source RAR is never modified.
        result = run_archive(args.archive, args.bearing_id, sevenzip=sevenzip)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
            output.write("\n")
        print(json.dumps({
            "research_only": True,
            "original_source_rar_and_80_mat_verified": True,
            "bearing_id": result["research_input_source"]["bearing_id"],
            "experimental_predicted_label": result["experimental_predicted_label"],
            "experimental_damage_model_score": result["experimental_damage_model_score"],
            "production_ml_approved": False,
            "output": str(args.out),
        }, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("EXPERIMENTAL_PADERBORN_ML_FAIL_CLOSED:", str(exc),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
