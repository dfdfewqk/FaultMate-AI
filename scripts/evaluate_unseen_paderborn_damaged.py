"""One-time strict external *damaged-only* evaluation of already frozen ML.

NEVER fits, selects a candidate, tunes a threshold, rewrites a model, or
treats 80 repeated measurements as 80 statistically independent bearings.
An original-MD5-verified eight-new-bearing cohort is required. Results
assess sensitivity only; specificity and false positive rate are undefined.
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

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_paderborn_assets import OFFICIAL_CONDITIONS, SourceAuditError
from scripts.extract_paderborn_unitless import FEATURE_NAMES, SCHEMA
from scripts.extract_unseen_paderborn_damaged import (
    KNOWN_NEW_MD5, MANIFEST, ORIGINAL_MODEL, PINNED_MODEL_SHA,
    canonical_json_sha256, verified_manifest,
)

HEX = re.compile(r"^[0-9a-f]{64}$")
KNOWN_TRAIN = {"K001", "K002", "K003", "K004", "K005",
               "KA04", "KA16", "KB23", "KI04", "KI16"}


def frozen_coefficients(path: Path = ORIGINAL_MODEL) -> dict:
    if path.resolve() != ORIGINAL_MODEL.resolve():
        raise SourceAuditError("only_original_frozen_model_allowed")
    if canonical_json_sha256(path) != PINNED_MODEL_SHA:
        raise SourceAuditError("frozen_model_sha256_mismatch")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if (doc.get("status") != "experimental_unapproved_not_for_runtime"
        or doc.get("approved_for_runtime") is not False
        or doc.get("runtime_inference_compatible") is not False
        or doc.get("source_numeric_si_units_verified") is not False
        or doc.get("field_generalization_proven") is not False
        or doc.get("original_feature_schema") != SCHEMA
        or doc.get("training_asset_count") != 10
        or set(doc.get("training_asset_ids", [])) != KNOWN_TRAIN
        or len(doc["training_asset_ids"]) != 10
        or doc.get("source_bearing_aggregate")
           != "median_of_all_4_conditions_80_original_trials_except_4_duplicates"
        or doc.get("source_cohort_license") != "CC BY-NC 4.0"
        or doc.get("decision_threshold_fixed") != .5
        or list(doc.get("feature_names", [])) != list(FEATURE_NAMES)):
        raise SourceAuditError("frozen_model_contract_mismatch")
    values = []
    for field in ("scaler_mean", "scaler_scale", "logistic_coefficients"):
        v = doc.get(field)
        if not isinstance(v, list) or len(v) != len(FEATURE_NAMES):
            raise SourceAuditError("invalid_frozen_vector:" + field)
        if any(type(x) not in (float, int) or not math.isfinite(x) for x in v):
            raise SourceAuditError("invalid_frozen_coefficients:" + field)
        values.append(np.asarray(v, dtype=float))
    if np.any(values[1] <= 0):
        raise SourceAuditError("invalid_frozen_scale")
    intercept = doc.get("logistic_intercept")
    if type(intercept) not in (float, int) or not math.isfinite(intercept):
        raise SourceAuditError("invalid_frozen_intercept")
    return {
        "mean": values[0], "scale": values[1],
        "coefs": values[2], "intercept": float(intercept),
        "threshold": .5, "model_sha256": PINNED_MODEL_SHA,
    }


def verify_new_reports(folder: Path, manifest_path: Path = MANIFEST):
    verified_manifest(manifest_path)
    if not folder.is_dir():
        raise SourceAuditError("unseen_feature_dir_missing")
    expected_files = {f"{asset}.json" for asset in KNOWN_NEW_MD5}
    found = {p.name for p in folder.iterdir() if p.is_file()}
    if found != expected_files:
        raise SourceAuditError("exact_eight_unseen_reports_required_no_prior_assets")
    result = {}
    all_fp = set()
    total = total_unique = duplicates = 0
    for asset in sorted(KNOWN_NEW_MD5):
        doc = json.loads((folder / (asset + ".json")).read_text(encoding="utf-8"))
        if (doc.get("schema") != SCHEMA
            or doc.get("evaluation_role") != "never_seen_damaged_only"
            or doc.get("status") != "real_original_unseen_damaged_features_unapproved"
            or doc.get("source_model_sha256") != PINNED_MODEL_SHA
            or doc.get("source_manifest_sha256") != canonical_json_sha256(manifest_path)
            or doc.get("label_source") != "Lessmeier et al. (2016), Table 5"
            or doc.get("bearing_id") != asset
            or doc.get("label") != "damaged"
            or doc.get("damage_origin") != "accelerated_lifetime"
            or doc.get("license") != "CC BY-NC 4.0"
            or doc.get("archive_verified") is not True
            or doc.get("official_archive_md5") != KNOWN_NEW_MD5[asset]
            or doc.get("source_recording_count") != 80
            or doc.get("raw_si_units_verified") is not False
            or doc.get("approved_for_runtime") is not False
            or doc.get("feature_names") != list(FEATURE_NAMES)):
            raise SourceAuditError("unseen_source_provenance_failed:" + asset)
        records = doc.get("records")
        if not isinstance(records, list) or len(records) != 80:
            raise SourceAuditError("unseen_80_original_mats_required:" + asset)
        named = set()
        local_first = {}
        local_dupes = []
        unique_features = []
        cond_trials = {}
        for entry in records:
            name = entry.get("recording")
            condition, trial = entry.get("condition"), entry.get("trial")
            if (name in named or condition not in OFFICIAL_CONDITIONS
                or type(trial) is not int or not 1 <= trial <= 20
                or name != f"{condition}_{asset}_{trial}.mat"):
                raise SourceAuditError("unseen_original_recording_name_invalid")
            named.add(name)
            cond_trials.setdefault(condition, set()).add(trial)
            fp = entry.get("source_raw_signal_fingerprint")
            mat_sha = entry.get("source_mat_sha256")
            if (not isinstance(fp, str) or not HEX.fullmatch(fp)
                or not isinstance(mat_sha, str) or not HEX.fullmatch(mat_sha)
                or type(entry.get("sample_count")) is not int
                or entry["sample_count"] < 16384):
                raise SourceAuditError("unseen_mat_signal_sha_or_sample_invalid")
            previous = local_first.get(fp)
            if entry.get("duplicate_of") != previous:
                raise SourceAuditError("unseen_duplicate_order_or_identity_invalid")
            if previous:
                if entry.get("values") is not None:
                    raise SourceAuditError("unseen_duplicate_not_excluded")
                duplicates += 1
                local_dupes.append({"recording": name, "duplicate_of": previous})
            else:
                if fp in all_fp:
                    raise SourceAuditError("unseen_cross_bearing_raw_signal_reuse")
                local_first[fp] = name
                all_fp.add(fp)
                feat = entry.get("values")
                if (not isinstance(feat, list) or len(feat) != 12
                    or any(type(x) not in (float, int) or not math.isfinite(x)
                           for x in feat)):
                    raise SourceAuditError("unseen_feature_vector_invalid")
                unique_features.append(feat)
            total += 1
        if (set(cond_trials) != OFFICIAL_CONDITIONS
            or any(trials != set(range(1, 21)) for trials in cond_trials.values())):
            raise SourceAuditError("unseen_four_conditions_incomplete")
        if doc.get("duplicates") != local_dupes or doc.get("unique_recording_count") != len(unique_features):
            raise SourceAuditError("unseen_duplicate_summary_mismatch")
        if len(unique_features) < 60:
            raise SourceAuditError("unseen_insufficient_unique_readings")
        total_unique += len(unique_features)
        result[asset] = np.asarray(unique_features, dtype=float)
    if total != 640 or total_unique + duplicates != 640:
        raise SourceAuditError("unseen_cohort_recording_count_invalid")
    return result, {"source_archives_verified": 8, "source_mat_files": total,
                    "source_unique_signal_pairs": total_unique,
                    "source_duplicates_removed": duplicates,
                    "physical_damaged_bearings": 8, "healthy_bearings": 0,
                    "primary_label_document": "Lessmeier 2016 Table 5",
                    "license": "CC BY-NC 4.0"}


def _wilson_interval(k: int, n: int, z: float = 1.959963984540054):
    if not n or k < 0 or k > n:
        raise ValueError("invalid_binary_interval")
    q = k / n
    den = 1 + z*z/n
    center = (q + z*z/(2*n)) / den
    half = z * math.sqrt(q*(1-q)/n + z*z/(4*n*n)) / den
    return [max(0., center-half), min(1., center+half)]


def evaluate(folder: Path, manifest_path: Path = MANIFEST):
    model = frozen_coefficients()
    signals, provenance = verify_new_reports(folder, manifest_path)
    predictions = []
    for asset in sorted(KNOWN_NEW_MD5):
        # Same multi-condition aggregation protocol as the frozen model.
        median = np.median(signals[asset], axis=0)
        z = (median - model["mean"]) / model["scale"]
        logit = float(np.dot(z, model["coefs"]) + model["intercept"])
        if logit >= 0:
            probability = 1.0 / (1.0 + math.exp(-logit))
        else:
            t = math.exp(logit)
            probability = t / (1.0 + t)
        damaged = probability >= model["threshold"]
        predictions.append({
            "asset_id": asset, "actual_label": "damaged",
            "predicted_label": "damaged" if damaged else "healthy",
            "missed_damaged": not damaged,
            "experimental_damage_probability": probability,
            "unique_source_recordings": len(signals[asset]),
        })
    detected = sum(not x["missed_damaged"] for x in predictions)
    n = len(predictions)
    return {
        "status": "one_time_unseen_damaged_only_sensitivity_no_model_approval",
        "frozen_model_sha256": PINNED_MODEL_SHA,
        "frozen_threshold": model["threshold"],
        "all_inputs_preregistered": True,
        "refitting_or_threshold_tuning_performed": False,
        "source": provenance, "predictions": predictions,
        "new_unseen_damaged_bearings": n,
        "damage_detected": detected, "damaged_missed": n-detected,
        "damaged_only_sensitivity": detected/n,
        "wilson_95pct_interval_damaged_only": _wilson_interval(detected, n),
        "new_healthy_bearings": 0,
        "specificity_measured": False,
        "false_alarm_rate_measured": False,
        "overall_accuracy_measured": False,
        "field_generalization_proven": False,
        "production_model_approved": False,
        "model_activated": False,
        "physical_si_units_verified": False,
        "warnings": [
            "All 8 unseen source assets have known accelerated-lifetime DAMAGE labels, none are new healthy assets.",
            "Damaged-only sensitivity is not general binary-class accuracy, specificity or field readiness.",
            "Same Paderborn bench/instrument family, not a second independent factory/site.",
            "Frozen research model expects 4 conditions/80 measurements; no single CSV sample inference.",
            "No missing SI units or gain/offset are invented.",
            "The previously used K006/KI18 test assets were excluded.",
            "Additional genuinely independent healthy bearings are needed for false alarm assessment.",
            "CC BY-NC 4.0 source data cannot be used commercially without separate permission.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--new-feature-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        report = evaluate(args.new_feature_dir)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(json.dumps({
            "status": report["status"],
            "new_independent_damaged_bearings": report["new_unseen_damaged_bearings"],
            "original_mat_records": report["source"]["source_mat_files"],
            "damage_detected": report["damage_detected"],
            "damaged_missed": report["damaged_missed"],
            "damaged_sensitivity_only": report["damaged_only_sensitivity"],
            "unseen_healthy_count": 0, "specificity_measured": False,
            "runtime_model_approved": False,
        }))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("UNSEEN_DAMAGE_EVALUATION_REJECTED_NO_METRICS:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
