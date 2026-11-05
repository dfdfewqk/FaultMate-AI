"""Train on REAL source-proven Paderborn raw unitless features; no SI or deploy claims.

Inputs: 12 *original-MD5-verified* feature reports AND the already existing
12 individually audited source MAT reports. Every source MAT SHA256 and raw
vibration/current fingerprint must match before any fitting.

Held-out physical bearings (NOT recording windows) are selected from a fixed
seed; test bearings are not used during fitting, threshold selection or LOBO
development. Real physical units are unresolved, so this is an EXPERIMENT,
not an authorized production diagnostic model. No runtime model is activated.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_paderborn_assets import CATALOG, OFFICIAL_CONDITIONS, SourceAuditError, validate_catalog
from scripts.extract_paderborn_unitless import SCHEMA, FEATURE_NAMES

SPLIT_SEED = 20261105
MODEL_C = 1.0
LABELS = ("healthy", "damaged")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_verified_unitless_cohort(
    feature_dir: Path, audits_dir: Path, catalog_path: Path = CATALOG
) -> tuple[list[dict], dict]:
    """Require exact matches to independently recorded raw MAT+signal evidence."""
    catalog = {x["id"]: x for x in validate_catalog(
        json.loads(catalog_path.read_text(encoding="utf-8")))}
    if not feature_dir.is_dir() or not audits_dir.is_dir():
        raise SourceAuditError("feature_or_source_audit_folder_missing")
    if sorted(p.name for p in feature_dir.glob("*.json")) != sorted(
        f"{asset}.json" for asset in catalog
    ):
        raise SourceAuditError("require_all_12_feature_reports")
    if sorted(p.name for p in audits_dir.glob("*.json")) != sorted(
        f"{asset}.json" for asset in catalog
    ):
        raise SourceAuditError("require_all_12_verified_original_mat_audits")
    rows = []
    unique_signals = {}
    hashes = []
    total_source = 0
    duplicate_total = 0
    for bearing_id, expected in sorted(catalog.items()):
        feat_path = feature_dir / f"{bearing_id}.json"
        audit_path = audits_dir / f"{bearing_id}.json"
        feature, audit = [json.loads(p.read_text(encoding="utf-8"))
                          for p in (feat_path, audit_path)]
        if (feature.get("schema") != SCHEMA
            or feature.get("status") != "real_raw_unitless_features_unreviewed"
            or feature.get("dataset") != "paderborn_bearing_datacenter"
            or feature.get("bearing_id") != bearing_id
            or feature.get("label") != expected["label"]
            or feature.get("license") != "CC BY-NC 4.0"
            or feature.get("official_archive_md5") != expected["md5"]
            or feature.get("archive_verified") is not True
            or feature.get("raw_si_units_verified") is not False
            or feature.get("si_amplitudes_used") is not False
            or feature.get("approved_for_runtime") is not False
            or list(feature.get("feature_names", [])) != list(FEATURE_NAMES)):
            raise SourceAuditError("unitless_feature_report_provenance_invalid:" + bearing_id)
        if (audit.get("bearing_id") != bearing_id
            or audit.get("label") != expected["label"]
            or audit.get("source_md5_verified") is not True
            or audit.get("source_archive_md5") != expected["md5"]
            or audit.get("inspected_recordings") != 80
            or audit.get("raw_units_verified") is not False
            or audit.get("approved_for_training") is not False):
            raise SourceAuditError("original_verified_raw_audit_missing_or_invalid:" + bearing_id)
        records = feature.get("records")
        raw_records = audit.get("recordings")
        if (not isinstance(records, list) or len(records) != 80
            or not isinstance(raw_records, list) or len(raw_records) != 80):
            raise SourceAuditError("incomplete_original_80_recordings:" + bearing_id)
        verified_raw = {r["recording"]: r for r in raw_records}
        if len(verified_raw) != 80:
            raise SourceAuditError("duplicate_original_audit_record_name:" + bearing_id)
        seen_names = set()
        local_signal_first = {}
        local_dupes = []
        for record in records:
            name = record.get("recording")
            condition = record.get("condition")
            trial = record.get("trial")
            if (name in seen_names or condition not in OFFICIAL_CONDITIONS
                or type(trial) is not int or not 1 <= trial <= 20
                or name != f"{condition}_{bearing_id}_{trial}.mat"):
                raise SourceAuditError("invalid_feature_recording_name:" + str(name))
            seen_names.add(name)
            raw = verified_raw.get(name)
            if raw is None:
                raise SourceAuditError("source_mat_without_original_audit:" + name)
            if (raw["mat_sha256"] != record.get("source_mat_sha256")
                or raw["raw_signal_fingerprint"] != record.get("source_raw_signal_fingerprint")
                or raw["sample_count"] != record.get("sample_count")
                or raw["condition"] != condition or raw["trial"] != trial):
                raise SourceAuditError("original_signal_provenance_mismatch:" + name)
            signal_fp = record["source_raw_signal_fingerprint"]
            local_previous = local_signal_first.get(signal_fp)
            if record.get("duplicate_of") != local_previous:
                raise SourceAuditError("duplicate_annotation_mismatch:" + name)
            if raw.get("duplicate_of") != local_previous:
                raise SourceAuditError("duplicate_raw_audit_mismatch:" + name)
            if local_previous:
                local_dupes.append({"recording": name, "duplicate_of": local_previous})
                if record.get("values") is not None:
                    raise SourceAuditError("duplicated_record_must_not_be_training_sample")
            else:
                local_signal_first[signal_fp] = name
                if signal_fp in unique_signals:
                    raise SourceAuditError("cross_bearing_raw_signal_reuse")
                unique_signals[signal_fp] = (bearing_id, name)
                values = record.get("values")
                if (not isinstance(values, list) or len(values) != len(FEATURE_NAMES)
                    or any(type(v) not in (int, float) or not np.isfinite(v)
                           for v in values)):
                    raise SourceAuditError("invalid_dimensionless_features:" + name)
                rows.append({"asset_id": bearing_id, "label": expected["label"],
                             "recording": name, "condition": condition,
                             "features": [float(v) for v in values]})
            total_source += 1
        if feature.get("duplicates") != local_dupes:
            raise SourceAuditError("feature_duplicate_list_mismatch:" + bearing_id)
        if (feature.get("source_recording_count") != 80
            or feature.get("unique_recording_count") != len(local_signal_first)
            or audit.get("duplicate_raw_recordings") != local_dupes):
            raise SourceAuditError("original_duplicate_record_count_mismatch:" + bearing_id)
        duplicate_total += len(local_dupes)
        hashes.append({"bearing_id": bearing_id, "feature_report_sha256": _sha256(feat_path),
                       "raw_audit_sha256": _sha256(audit_path),
                       "verified_source_archive_md5": expected["md5"]})
    if (total_source != 960 or duplicate_total != 4 or len(rows) != 956
        or len(unique_signals) != 956):
        raise SourceAuditError("expected_960_raw_956_unique_and_4_duplicates")
    if (Counter(row["label"] for row in rows)
        != {"healthy": 480, "damaged": 476}):
        raise SourceAuditError("expected_original_cohort_label_counts")
    return rows, {"source_bearings": 12, "source_recordings": 960,
                  "unique_recordings": 956, "duplicates_dropped": 4,
                  "labels_by_physical_bearing": {"healthy": 6, "damaged": 6},
                  "source_audit_sha256": hashes,
                  "license": "CC BY-NC 4.0", "physical_si_units_verified": False}


def independent_split(rows: list[dict]) -> dict:
    """Predetermined seed, one dev-validation and one sealed test per class."""
    rng = np.random.RandomState(SPLIT_SEED)
    by_label = {x: sorted({r["asset_id"] for r in rows if r["label"] == x})
                for x in LABELS}
    if any(len(by_label[x]) != 6 for x in LABELS):
        raise SourceAuditError("expected_six_independent_bearings_per_class")
    train, validation, test = [], [], []
    for label in LABELS:
        values = by_label[label][:]
        rng.shuffle(values)
        train.extend(values[:4])
        validation.append(values[4])
        test.append(values[5])
    return {"train": sorted(train), "validation": sorted(validation), "test": sorted(test)}


def _fit(rows: list[dict], assets: list[str]):
    selected = [r for r in rows if r["asset_id"] in assets]
    unique = {r["asset_id"] for r in selected}
    if unique != set(assets):
        raise SourceAuditError("missing_training_assets")
    counts = Counter(x["asset_id"] for x in selected)
    if {x["label"] for x in selected} != set(LABELS):
        raise SourceAuditError("both_training_labels_required")
    x = np.asarray([r["features"] for r in selected])
    y = np.asarray([int(r["label"] == "damaged") for r in selected])
    # Every physical bearing contributes equal total sample weight.
    weights = np.asarray([1. / counts[r["asset_id"]] for r in selected])
    scaler = StandardScaler().fit(x)
    x_train = scaler.transform(x)
    classifier = LogisticRegression(
        C=MODEL_C, class_weight=None, random_state=SPLIT_SEED, max_iter=3000)
    classifier.fit(x_train, y, sample_weight=weights)
    return scaler, classifier


def _bearings_predict(rows, assets, model):
    scaler, classifier = model
    actual, predicted, details = [], [], []
    for asset in sorted(assets):
        selected = [r for r in rows if r["asset_id"] == asset]
        if not selected:
            raise SourceAuditError("missing_evaluation_asset")
        y = LABELS.index(selected[0]["label"])
        if any(LABELS.index(r["label"]) != y for r in selected):
            raise SourceAuditError("mixed_labels_within_bearing")
        p = classifier.predict_proba(
            scaler.transform(np.asarray([r["features"] for r in selected])))[:, 1]
        score = float(np.median(p))
        vote = int(score >= .5)
        actual.append(y)
        predicted.append(vote)
        details.append({"asset_id": asset, "true_label": LABELS[y],
                        "predicted_label": LABELS[vote],
                        "damaged_probability_experimental": score,
                        "recordings": len(selected)})
    return actual, predicted, details


def _metrics(actual, predicted):
    m = confusion_matrix(actual, predicted, labels=[0, 1]).tolist()
    return {"independent_bearing_count": len(actual),
            "accuracy": float(accuracy_score(actual, predicted)),
            "macro_f1": float(f1_score(actual, predicted, average="macro",
                                      labels=[0, 1], zero_division=0)),
            "confusion_matrix_labels": LABELS,
            "confusion_matrix": m,
            "damaged_missed_count": m[1][0],
            "healthy_false_alarm_count": m[0][1]}


def train_real_unitless(feature_dir: Path, audit_dir: Path, out_dir: Path,
                        catalog_path: Path = CATALOG):
    """No overwrite. Experimental coefficients NOT accepted by app ML loader."""
    rows, provenance = load_verified_unitless_cohort(feature_dir, audit_dir, catalog_path)
    split = independent_split(rows)
    train_assets = split["train"]
    dev_assets = sorted(train_assets + split["validation"])
    test_assets = split["test"]
    assert not set(dev_assets).intersection(test_assets)
    assert len(dev_assets) == 10 and len(test_assets) == 2

    # Fixed model, no hyperparameter search using test. Independent development
    # cross-validation on each of the 10 different physical dev bearings.
    dev_true, dev_pred, dev_detail = [], [], []
    for heldout in dev_assets:
        fold_assets = [b for b in dev_assets if b != heldout]
        actual, prediction, detail = _bearings_predict(
            rows, [heldout], _fit(rows, fold_assets))
        dev_true.extend(actual)
        dev_pred.extend(prediction)
        dev_detail.extend(detail)

    final_model = _fit(rows, dev_assets)
    test_true, test_pred, test_detail = _bearings_predict(
        rows, test_assets, final_model)
    scaler, classifier = final_model
    experimental = {
        "status": "experimental_unapproved_do_not_load",
        "trained_on_real_verified_paderborn_measurements": True,
        "source_numeric_si_units_verified": False,
        "source_cohort_license": "CC BY-NC 4.0",
        "source_recordings": 960, "unique_recordings": 956,
        "physical_bearings_in_training": len(dev_assets),
        "feature_schema": SCHEMA, "feature_names": FEATURE_NAMES,
        "threshold_fixed_not_optimized": .5,
        "split_seed": SPLIT_SEED,
        "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(),
        "logistic_coefficients": classifier.coef_[0].tolist(),
        "logistic_intercept": float(classifier.intercept_[0]),
        "not_a_validated_model": True, "no_runtime_activation": True,
    }
    report = {
        "status": "real_source_experimental_training_finished_no_runtime_approval",
        "provenance": provenance, "feature_schema": SCHEMA,
        "independent_split": split, "fixed_algorithm": {
            "name": "standard_scaled_logistic_regression",
            "C": MODEL_C, "threshold": .5, "random_seed": SPLIT_SEED,
            "row_weighting": "equal_total_weight_per_physical_bearing",
        },
        "train_reused_holdout": False,
        "development_leave_one_bearing_out": {
            "metrics": _metrics(dev_true, dev_pred), "predictions": dev_detail,
            "basis": "10 dev physical bearings; fitted without each held-out bearing",
        },
        "sealed_test": {
            "metrics": _metrics(test_true, test_pred), "predictions": test_detail,
            "basis": "2 unseen physical bearings, one per class; extremely low precision",
        },
        "ml_model_approved": False,
        "external_field_generalization_demonstrated": False,
        "limitations": [
            "Only 12 unique physical bearings, not 956 statistically independent assets.",
            "Two independent sealed test bearings are insufficient for deployment.",
            "Unknown raw signal calibration makes amplitude-based field interpretation invalid.",
            "Dimensionless features are not equivalent to calibrated vibration/current.",
            "Labels are original bearing-level condition; no universal motor fault diagnosis.",
            "Dataset is CC BY-NC 4.0 and cannot be used commercially without permission.",
        ],
    }
    if out_dir.exists():
        raise SourceAuditError("output_folder_exists_do_not_overwrite_prior_evaluation")
    out_dir.mkdir(parents=True)
    with (out_dir / "real_unitless_evaluation.json").open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with (out_dir / "experimental_unapproved_model.json").open("x", encoding="utf-8") as f:
        json.dump(experimental, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("REAL_RAW_UNITLESS_ML_EXPERIMENT_COMPLETE_NOT_APPROVED")
    print(json.dumps({
        "source_bearings": 12, "source_recordings": 960,
        "unique_recordings": 956, "removed_duplicates": 4,
        "train_bearings": len(dev_assets), "test_bearings": 2,
        "dev_lobo_macro_f1": report["development_leave_one_bearing_out"]["metrics"]["macro_f1"],
        "test_bearing_macro_f1": report["sealed_test"]["metrics"]["macro_f1"],
        "test_bearing_accuracy": report["sealed_test"]["metrics"]["accuracy"],
        "test_missed_damaged": report["sealed_test"]["metrics"]["damaged_missed_count"],
        "test_false_damage_alarm": report["sealed_test"]["metrics"]["healthy_false_alarm_count"],
        "activated": False, "si_units_verified": False,
    }, ensure_ascii=False))
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feature-dir", type=Path, required=True)
    p.add_argument("--raw-audits-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--catalog", type=Path, default=CATALOG)
    args = p.parse_args(argv)
    try:
        train_real_unitless(args.feature_dir, args.raw_audits_dir,
                            args.out, args.catalog)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as e:
        print("REAL_UNITLESS_TRAINING_FAILED_NO_CLAIM:", str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
