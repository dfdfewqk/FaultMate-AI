"""Experimental Paderborn development-only improvement: physical-bearing aggregation.

Inputs are ONLY the ten already-opened development bearings from the verified
2026-11-05 real-source run. Previously opened K006/KI18 sealed test recordings
are explicitly excluded from all development input, fitting and selection.

No SI-unit claims, no industrial field validation, no runtime model promotion.
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
from scripts.audit_paderborn_assets import (
    CATALOG, OFFICIAL_CONDITIONS, SourceAuditError, validate_catalog,
)
from scripts.extract_paderborn_unitless import FEATURE_NAMES, SCHEMA
from scripts.train_paderborn_unitless import SPLIT_SEED

# Pin to the prior SUCCESSFUL real-source run. This is a trusted, immutable
# development fixture identity, not a hash of the model's prediction numbers.
BASELINE_REPORT_SHA256 = "f52fb71ec166d056ccad610cbbe991660c63ab98e147a7e45147f0e802a6452c"
BASELINE_RUN_ID = 41965647928
PREVIOUSLY_OPENED_TEST_BEARINGS = frozenset(("K006", "KI18"))
MODEL_C = 1.0
THRESHOLD = .5
LABELS = ("healthy", "damaged")
# Exactly four interpretable, frozen candidates. Candidate set is exploratory
# and was proposed after examining the 10 development bearings; do NOT treat
# inner/nested CV as an unbiased prospective external evaluation.
CANDIDATES = (
    ("record_level_logistic_all", "record", tuple(range(12))),
    ("bearing_median_logistic_all", "bearing", tuple(range(12))),
    ("bearing_median_logistic_spectral", "bearing", (3, 4, 5, 9, 10, 11)),
    ("bearing_spectral_nearest_centroid", "centroid", (3, 4, 5, 9, 10, 11)),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_dev_rows(feature_dir: Path, audit_dir: Path, baseline: Path,
                      *, baseline_sha256: str = BASELINE_REPORT_SHA256,
                      catalog_path: Path = CATALOG):
    """Require all ten baseline development assets, never the opened test set."""
    if _sha256(baseline) != baseline_sha256:
        raise SourceAuditError("baseline_real_source_evaluation_hash_mismatch")
    prior = json.loads(baseline.read_text(encoding="utf-8"))
    src = prior.get("provenance", {})
    split = prior.get("independent_split", {})
    if (prior.get("status") != "real_source_experimental_training_finished_no_runtime_approval"
        or prior.get("ml_model_approved") is not False
        or prior.get("feature_schema") != SCHEMA
        or src.get("source_bearings") != 12
        or src.get("source_recordings") != 960
        or src.get("unique_recordings") != 956
        or src.get("duplicates_dropped") != 4
        or src.get("physical_si_units_verified") is not False
        or src.get("license") != "CC BY-NC 4.0"):
        raise SourceAuditError("prior_source_evaluation_not_proven")
    catalog = {r["id"]: r for r in validate_catalog(
        json.loads(catalog_path.read_text(encoding="utf-8")))}
    training = split.get("train")
    validation = split.get("validation")
    test = split.get("test")
    if (not isinstance(training, list) or not isinstance(validation, list)
        or not isinstance(test, list)
        or len(training) != 8 or len(validation) != 2 or len(test) != 2
        or len(set(training + validation + test)) != 12
        or set(training + validation + test) != set(catalog)
        or set(test) != PREVIOUSLY_OPENED_TEST_BEARINGS
        or split.get("train_reused_holdout") is True):
        raise SourceAuditError("original_bearing_split_untrusted")
    dev = sorted(set(training + validation))
    if not feature_dir.is_dir() or not audit_dir.is_dir():
        raise SourceAuditError("dev_source_paths_missing")
    expected_files = sorted(f"{asset}.json" for asset in dev)
    if (sorted(p.name for p in feature_dir.glob("*.json")) != expected_files
        or sorted(p.name for p in audit_dir.glob("*.json")) != expected_files):
        raise SourceAuditError("dev_only_exact_10_reports_required_no_test_bearings")
    hashes = src.get("source_audit_sha256")
    if (not isinstance(hashes, list) or len(hashes) != 12
        or {d.get("bearing_id") for d in hashes} != set(catalog)):
        raise SourceAuditError("missing_original_source_fingerprints")
    known = {d["bearing_id"]: d for d in hashes}
    catalog_sha = _sha256(catalog_path)
    rows = []
    seen_global = set()
    duplicates = []
    for asset in dev:
        info = known[asset]
        feat_path = feature_dir / f"{asset}.json"
        audit_path = audit_dir / f"{asset}.json"
        if (_sha256(feat_path) != info["feature_report_sha256"]
            or _sha256(audit_path) != info["raw_audit_sha256"]):
            raise SourceAuditError("original_real_source_blob_sha_mismatch:" + asset)
        feat = json.loads(feat_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        # Named assertions preserve the same strict gates and identify which
        # source metadata check failed without disclosing any raw measurement.
        checks = {
            "schema": feat.get("schema") == SCHEMA,
            "bearing_id": feat.get("bearing_id") == asset,
            "feature_status": feat.get("status") == "real_raw_unitless_features_unreviewed",
            "dataset": feat.get("dataset") == "paderborn_bearing_datacenter",
            "label": feat.get("label") == catalog[asset]["label"],
            "license": feat.get("license") == "CC BY-NC 4.0",
            "catalog_sha": feat.get("source_catalog_sha256") == catalog_sha,
            "archive_md5": feat.get("official_archive_md5") == catalog[asset]["md5"],
            "archive_verified": feat.get("archive_verified") is True,
            "raw_si_unverified": feat.get("raw_si_units_verified") is False,
            "si_amplitudes_not_claimed": feat.get("si_amplitudes_used") is False,
            "model_not_approved": feat.get("approved_for_runtime") is False,
            "feature_names": list(feat.get("feature_names", [])) == list(FEATURE_NAMES),
            "audit_asset": audit.get("bearing_id") == asset,
            "audit_label": audit.get("label") == catalog[asset]["label"],
            "audit_source_md5": audit.get("source_md5_verified") is True,
            "audit_archive_md5": audit.get("source_archive_md5") == catalog[asset]["md5"],
            "audit_raw_si_unverified": audit.get("raw_units_verified") is False,
            "audit_not_training_approved": audit.get("approved_for_training") is False,
        }
        bad = [name for name, valid in checks.items() if not valid]
        if bad:
            raise SourceAuditError(
                "original_source_fields_invalid:" + asset + ":" + ",".join(bad))
        records = feat.get("records")
        audits = audit.get("recordings")
        if (not isinstance(records, list) or len(records) != 80
            or not isinstance(audits, list) or len(audits) != 80
            or feat.get("source_recording_count") != 80
            or audit.get("inspected_recordings") != 80):
            raise SourceAuditError("incomplete_mat_records:" + asset)
        by_name = {r["recording"]: r for r in audits}
        if len(by_name) != 80:
            raise SourceAuditError("duplicated_audit_mat_file:" + asset)
        local_seen = {}
        local_dups = []
        seen_names = set()
        for entry in records:
            name = entry.get("recording")
            condition = entry.get("condition")
            trial = entry.get("trial")
            if (name in seen_names or condition not in OFFICIAL_CONDITIONS
                or type(trial) is not int or not 1 <= trial <= 20
                or name != f"{condition}_{asset}_{trial}.mat"):
                raise SourceAuditError("invalid_original_mat_record:" + str(name))
            seen_names.add(name)
            raw = by_name.get(name)
            if raw is None:
                raise SourceAuditError("missing_original_mat_reference:" + name)
            for feature_key, audit_key in (
                ("source_mat_sha256", "mat_sha256"),
                ("source_raw_signal_fingerprint", "raw_signal_fingerprint"),
                ("sample_count", "sample_count"),
                ("condition", "condition"), ("trial", "trial"),
                ("duplicate_of", "duplicate_of"),
            ):
                if entry.get(feature_key) != raw.get(audit_key):
                    raise SourceAuditError("source_measurement_mismatch:" + name)
            fingerprint = entry["source_raw_signal_fingerprint"]
            first = local_seen.get(fingerprint)
            if entry["duplicate_of"] != first:
                raise SourceAuditError("raw_duplicate_order_mismatch:" + name)
            if first is not None:
                if entry.get("values") is not None:
                    raise SourceAuditError("duplicate_raw_training_row:" + name)
                local_dups.append({"recording": name, "duplicate_of": first})
                duplicates.append(name)
            else:
                if fingerprint in seen_global:
                    raise SourceAuditError("cross_asset_mat_signal_duplicate")
                local_seen[fingerprint] = name
                seen_global.add(fingerprint)
                values = entry.get("values")
                if (not isinstance(values, list)
                    or len(values) != len(FEATURE_NAMES)
                    or any(type(v) not in (int, float) or not np.isfinite(v)
                           for v in values)):
                    raise SourceAuditError("invalid_unscaled_feature_values:" + name)
                rows.append({"asset_id": asset, "label": feat["label"],
                             "condition": condition, "recording": name,
                             "features": [float(v) for v in values]})
        if (feat.get("duplicates") != local_dups
            or audit.get("duplicate_raw_recordings") != local_dups
            or feat.get("unique_recording_count") != len(local_seen)):
            raise SourceAuditError("real_duplicate_annotation_mismatch:" + asset)
    labels = Counter({a: catalog[a]["label"] for a in dev}.values())
    if (len(rows) != 796 or len(duplicates) != 4
        or labels != {"healthy": 5, "damaged": 5}):
        raise SourceAuditError("expected_10_development_bearings_796_unique_records")
    return rows, {"dev_assets": dev, "test_asset_ids_excluded": sorted(test),
                  "input_recordings": 800, "unique_recordings": 796,
                  "duplicate_exclusions": 4, "physical_bearings": 10,
                  "original_real_ci_run_id": BASELINE_RUN_ID,
                  "baseline_evaluation_sha256": baseline_sha256,
                  "source_physical_si_units_verified": False,
                  "approved_for_runtime": False}


def _split_rows(rows: list[dict], assets: list[str]):
    return [r for r in rows if r["asset_id"] in set(assets)]


def _bearing_vector(rows: list[dict], asset: str, features: tuple[int, ...],
                    *, condition: str | None = None):
    records = [r for r in rows if r["asset_id"] == asset
               and (condition is None or r["condition"] == condition)]
    if not records:
        raise SourceAuditError("bearing_or_condition_missing:" + asset)
    return np.median(np.asarray([r["features"] for r in records])[:, list(features)], axis=0)


def _predict(rows: list[dict], train: list[str], test: str, config,
             *, condition: str | None = None) -> float:
    label_by_asset = {r["asset_id"]: int(r["label"] == "damaged") for r in rows}
    if not test or test in train or len(set(train)) != len(train):
        raise SourceAuditError("evaluation_asset_leakage")
    if set(label_by_asset) < set(train + [test]):
        raise SourceAuditError("missing_eval_assets")
    if {label_by_asset[a] for a in train} != {0, 1}:
        raise SourceAuditError("both_train_classes_required")
    name, method, feature_indices = config
    feature_indices = tuple(feature_indices)
    if method == "record":
        selected = [r for r in rows if r["asset_id"] in train
                    and (condition is None or r["condition"] == condition)]
        counts = Counter(r["asset_id"] for r in selected)
        x_train = np.asarray([r["features"] for r in selected])[:, list(feature_indices)]
        y_train = np.asarray([label_by_asset[r["asset_id"]] for r in selected])
        weights = np.asarray([1. / counts[r["asset_id"]] for r in selected])
        x_test = np.asarray([r["features"] for r in rows if r["asset_id"] == test
                             and (condition is None or r["condition"] == condition)]
                            )[:, list(feature_indices)]
    else:
        x_train = np.asarray([_bearing_vector(rows, a, feature_indices,
                                               condition=condition) for a in train])
        y_train = np.asarray([label_by_asset[a] for a in train])
        weights = None
        x_test = _bearing_vector(rows, test, feature_indices,
                                 condition=condition).reshape(1, -1)
    scaler = StandardScaler().fit(x_train)
    train_z = scaler.transform(x_train)
    test_z = scaler.transform(x_test)
    if method == "centroid":
        means = [np.mean(train_z[y_train == i], axis=0) for i in (0, 1)]
        distances = [float(np.sum((test_z[0] - means[i]) ** 2)) for i in (0, 1)]
        denom = sum(distances)
        return float(distances[0] / denom) if denom else .5
    if method not in ("record", "bearing"):
        raise SourceAuditError("unknown_comparison_method")
    model = LogisticRegression(C=MODEL_C, random_state=SPLIT_SEED,
                               max_iter=3000)
    model.fit(train_z, y_train, sample_weight=weights)
    estimates = model.predict_proba(test_z)[:, 1]
    return float(np.median(estimates))


def _metrics(actual: list[int], predicted: list[int]):
    confusion = confusion_matrix(actual, predicted, labels=[0, 1]).tolist()
    return {
        "physical_bearings": len(actual),
        "accuracy": float(accuracy_score(actual, predicted)),
        "macro_f1": float(f1_score(actual, predicted, labels=[0, 1],
                                    average="macro", zero_division=0)),
        "confusion_matrix_labels": LABELS,
        "confusion_matrix": confusion,
        "healthy_false_alarms": confusion[0][1],
        "damaged_misses": confusion[1][0],
    }


def _lobo(rows, assets, candidate, *, condition=None):
    actual, predicted, scores = [], [], []
    labels = {r["asset_id"]: int(r["label"] == "damaged") for r in rows}
    for excluded in sorted(assets):
        training = [a for a in assets if a != excluded]
        p = _predict(rows, training, excluded, candidate, condition=condition)
        actual.append(labels[excluded])
        predicted.append(int(p >= THRESHOLD))
        scores.append({
            "asset_id": excluded,
            "real_label": LABELS[labels[excluded]],
            "predicted_label": LABELS[int(p >= THRESHOLD)],
            "experimental_damaged_score": p,
        })
    return _metrics(actual, predicted), scores


def analyze_development(rows: list[dict], provenance: dict):
    dev = sorted(provenance["dev_assets"])
    expected = sorted({r["asset_id"] for r in rows})
    if len(dev) != 10 or dev != expected:
        raise SourceAuditError("development_data_scope_invalid")
    if set(dev).intersection(PREVIOUSLY_OPENED_TEST_BEARINGS):
        raise SourceAuditError("sealed_test_data_in_training")
    if Counter({r["asset_id"]: r["label"] for r in rows}.values()) != {
        "healthy": 5, "damaged": 5
    }:
        raise SourceAuditError("development_labels_unbalanced")
    candidates = {}
    for cfg in CANDIDATES:
        metrics, predictions = _lobo(rows, dev, cfg)
        candidates[cfg[0]] = {"metrics": metrics, "predictions": predictions}

    # Candidate selection is nested *within development data only*, but
    # candidates were devised after the first development diagnostics: this
    # remains exploratory/model-selection evidence, NOT independent validation.
    labels = {r["asset_id"]: int(r["label"] == "damaged") for r in rows}
    selections, actual, predicted = [], [], []
    for outer_bearing in dev:
        inner_assets = [a for a in dev if a != outer_bearing]
        rankings = []
        for index, cfg in enumerate(CANDIDATES):
            inner_metrics, _ = _lobo(rows, inner_assets, cfg)
            rankings.append((inner_metrics["macro_f1"],
                             -inner_metrics["damaged_misses"],
                             -inner_metrics["healthy_false_alarms"],
                             -index, cfg))
        chosen = max(rankings)[-1]
        p = _predict(rows, inner_assets, outer_bearing, chosen)
        vote = int(p >= THRESHOLD)
        actual.append(labels[outer_bearing])
        predicted.append(vote)
        selections.append({"asset_id": outer_bearing, "candidate": chosen[0],
                           "true_label": LABELS[labels[outer_bearing]],
                           "predicted_label": LABELS[vote],
                           "experimental_damaged_score": p,
                           "inner_selection_did_not_see_outer_bearing": True})

    # Operate on one condition per bearing, with 20 different original trials.
    # This is a robustness diagnostic, not a new split or independent test.
    all_features = CANDIDATES[1]
    condition_stress = {}
    for cond in sorted(OFFICIAL_CONDITIONS):
        metrics, preds = _lobo(rows, dev, all_features, condition=cond)
        condition_stress[cond] = {"metrics": metrics, "predictions": preds}

    # Freeze the simple bearing-median logistic baseline as an experimental
    # candidate only. It requires repeated readings, not a single sensor value.
    matrix = np.asarray([_bearing_vector(rows, a, tuple(range(12))) for a in dev])
    y = np.asarray([labels[a] for a in dev])
    scaler = StandardScaler().fit(matrix)
    fit = LogisticRegression(C=MODEL_C, random_state=SPLIT_SEED,
                             max_iter=3000).fit(scaler.transform(matrix), y)
    provisional_model = {
        "status": "experimental_unapproved_not_for_runtime",
        "training_asset_ids": dev,
        "training_asset_count": 10,
        "source_bearing_aggregate": "median_of_all_4_conditions_80_original_trials_except_4_duplicates",
        "original_feature_schema": SCHEMA,
        "feature_names": list(FEATURE_NAMES),
        "source_numeric_si_units_verified": False,
        "source_cohort_license": "CC BY-NC 4.0",
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "logistic_coefficients": fit.coef_[0].tolist(),
        "logistic_intercept": float(fit.intercept_[0]),
        "decision_threshold_fixed": THRESHOLD,
        "runtime_inference_compatible": False,
        "approved_for_runtime": False,
        "field_generalization_proven": False,
    }
    report = {
        "status": "exploratory_development_comparison_no_independent_new_test",
        "source": provenance,
        "candidate_models_considered": [c[0] for c in CANDIDATES],
        "development_only_lobo": candidates,
        "nested_development_selection": {
            "metrics": _metrics(actual, predicted),
            "predictions": selections,
            "note": "Exploratory, since candidate family was shaped after seeing development errors.",
        },
        "per_condition_robustness": condition_stress,
        "physical_si_units_verified": False,
        "previously_opened_heldout_reused": False,
        "new_independent_external_evaluation": False,
        "production_approved": False,
        "limitations": [
            "Ten related development bearings are not evidence of industrial field performance.",
            "Candidate families were examined after prior errors: optimistic model-selection bias.",
            "Previous two heldout bearings are already opened and cannot be claimed as a new test.",
            "The new bearing-level model needs multiple original measurements across 4 conditions.",
            "Original current/acceleration numerical SI calibration is unverified.",
            "Only license-bound Paderborn educational/non-commercial research use is supported.",
        ],
    }
    return report, provisional_model


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feature-dir", type=Path, required=True)
    p.add_argument("--raw-audits-dir", type=Path, required=True)
    p.add_argument("--original-evaluation", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        rows, provenance = verified_dev_rows(
            args.feature_dir, args.raw_audits_dir, args.original_evaluation)
        report, model = analyze_development(rows, provenance)
        if args.out.exists():
            raise SourceAuditError("output_folder_exists_no_overwrite")
        args.out.mkdir(parents=True)
        with (args.out / "development_comparison.json").open(
                "x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")
        with (args.out / "development_aggregated_unapproved.json").open(
                "x", encoding="utf-8") as f:
            json.dump(model, f, indent=2, ensure_ascii=False)
            f.write("\n")
        baseline = report["development_only_lobo"][CANDIDATES[0][0]]["metrics"]
        improved = report["development_only_lobo"][CANDIDATES[1][0]]["metrics"]
        nested = report["nested_development_selection"]["metrics"]
        print(json.dumps({
            "status": "exploratory_only_no_new_independent_test",
            "dev_bearings": 10,
            "source_records_unique": provenance["unique_recordings"],
            "baseline_lobo_accuracy": baseline["accuracy"],
            "bearing_median_lobo_accuracy": improved["accuracy"],
            "nested_dev_accuracy": nested["accuracy"],
            "source_units_verified": False,
            "model_activated": False,
        }))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        print("DEVELOPMENT_COMPARISON_FAILED_NO_PUBLISHED_MODEL:", str(e),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
