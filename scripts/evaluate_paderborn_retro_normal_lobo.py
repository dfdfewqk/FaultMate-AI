"""Retrospective 12-physical-bearing normal/miss audit, NEVER prospective validation.

Only previously extracted, original-MD5-verified Paderborn study summaries are
used. Source reports and *each* feature/audit file must match the SHA256 manifest
from the previous real-source experiment. All 12 physical bearings have ALREADY
been opened; the classifier and selection were informed by earlier outcomes.

Re-fitting for each leave-one-physical-bearing-out (LOBO) fold is an exploratory
diagnostic only. No model weights, source files, or runtime approval are written.
The output cannot establish fresh independent specificity or field performance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from math import sqrt
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_paderborn_assets import SourceAuditError
from scripts.evaluate_unitless_dev_only import (
    BASELINE_REPORT_SHA256,
    CANDIDATES,
    _lobo,
)
from scripts.train_paderborn_unitless import LABELS, load_verified_unitless_cohort
from scripts.evaluate_unseen_paderborn_damaged import frozen_coefficients

SCHEMA = "faultmate_retrospective_opened_12_bearing_lobo_v1"
EXPECTED_DEVELOPMENT = frozenset((
    "K001", "K002", "K003", "K004", "K005",
    "KA04", "KA16", "KB23", "KI04", "KI16",
))
EXPECTED_PRIOR_TEST = frozenset(("K006", "KI18"))
FROZEN_CANDIDATE = "bearing_median_logistic_all"
BASELINE_PRIOR_RUN = 41965647928
REAL_AUDIT_PRIOR_RUN = 41957475830


def sha256(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise SourceAuditError("source_report_missing_or_symlink")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson_interval(successes: int, trials: int) -> list[float]:
    """Two-sided 95% Wilson interval for descriptive Bernoulli proportions."""
    if (type(successes) is not int or type(trials) is not int
        or trials < 1 or successes < 0 or successes > trials):
        raise ValueError("invalid_bernoulli_counts")
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half_width = z * sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return [max(0.0, center - half_width), min(1.0, center + half_width)]


def verify_previous_evidence(feature_dir: Path, audits_dir: Path, baseline: Path):
    """Pin the ORIGINAL 12 source-derived feature/audit files to the older run."""
    if sha256(baseline) != BASELINE_REPORT_SHA256:
        raise SourceAuditError("prior_real_model_evaluation_sha_mismatch")
    prior = json.loads(baseline.read_text(encoding="utf-8"))
    provenance = prior.get("provenance", {})
    split = prior.get("independent_split", {})
    if (prior.get("status") != "real_source_experimental_training_finished_no_runtime_approval"
        or prior.get("ml_model_approved") is not False
        or provenance.get("source_recordings") != 960
        or provenance.get("unique_recordings") != 956
        or provenance.get("duplicates_dropped") != 4
        or provenance.get("physical_si_units_verified") is not False
        or set(split.get("train", []) + split.get("validation", [])) != EXPECTED_DEVELOPMENT
        or set(split.get("test", [])) != EXPECTED_PRIOR_TEST):
        raise SourceAuditError("old_study_original_scope_or_approval_changed")

    manifest = provenance.get("source_audit_sha256")
    if (not isinstance(manifest, list) or len(manifest) != 12
        or {d.get("bearing_id") for d in manifest if isinstance(d, dict)}
            != EXPECTED_DEVELOPMENT | EXPECTED_PRIOR_TEST):
        raise SourceAuditError("prior_source_manifest_not_full_12")
    for d in manifest:
        if (sha256(feature_dir / (d["bearing_id"] + ".json"))
                != d.get("feature_report_sha256")
            or sha256(audits_dir / (d["bearing_id"] + ".json"))
                != d.get("raw_audit_sha256")):
            raise SourceAuditError("prior_artifact_sha_mismatch:" + d["bearing_id"])
    rows, source = load_verified_unitless_cohort(feature_dir, audits_dir)
    if (source.get("source_bearings") != 12 or source.get("unique_recordings") != 956
        or source.get("physical_si_units_verified") is not False):
        raise SourceAuditError("unverified_cohort")
    return rows, source


def retrospective_group_lobo(rows: list[dict]) -> dict:
    """One prediction per physical bearing, never per 4s recording/window."""
    labels = {r["asset_id"]: r["label"] for r in rows}
    assets = sorted(labels)
    if (len(assets) != 12
        or set(assets) != EXPECTED_DEVELOPMENT | EXPECTED_PRIOR_TEST
        or Counter(labels.values()) != {"healthy": 6, "damaged": 6}
        or len(rows) != 956
        or any(r["label"] != labels[r["asset_id"]] for r in rows)
        or Counter(r["asset_id"] for r in rows) !=
           Counter({asset: 76 if asset == "KA04" else 80 for asset in assets})):
        raise SourceAuditError("retrospective_bearing_population_or_groups_invalid")
    cfg = next((x for x in CANDIDATES if x[0] == FROZEN_CANDIDATE), None)
    if cfg is None or cfg[1] != "bearing" or tuple(cfg[2]) != tuple(range(12)):
        raise SourceAuditError("previous_development_candidate_changed")
    metrics, predictions = _lobo(rows, assets, cfg)
    if (metrics["physical_bearings"] != 12
        or len(predictions) != 12
        or {p["asset_id"] for p in predictions} != set(assets)):
        raise SourceAuditError("missing_bearing_level_predictions")
    matrix = metrics["confusion_matrix"]  # actual healthy/damaged by predicted healthy/damaged
    tn, fp = matrix[0]
    fn, tp = matrix[1]
    if (tn + fp != 6 or tp + fn != 6
        or metrics["healthy_false_alarms"] != fp
        or metrics["damaged_misses"] != fn):
        raise SourceAuditError("retrospective_confusion_matrix_invalid")
    return {
        "candidate_selected_using_historical_development_outcomes": True,
        "model_refit_each_group_fold": True,
        "fixed_non_tuned_classification_threshold": 0.5,
        "independent_unit_is_physical_bearing_not_measurement": True,
        "metrics": metrics,
        "descriptive_healthy_specificity": tn / 6,
        "descriptive_healthy_specificity_wilson95": wilson_interval(tn, 6),
        "descriptive_damage_sensitivity": tp / 6,
        "descriptive_damage_sensitivity_wilson95": wilson_interval(tp, 6),
        "fold_predictions": predictions,
    }


def evaluate_historical_artifacts(
    feature_dir: Path, audits_dir: Path, baseline: Path
) -> dict:
    # Prove the known pinned frozen model has not silently been replaced.
    model = frozen_coefficients()
    rows, provenance = verify_previous_evidence(feature_dir, audits_dir, baseline)
    study = retrospective_group_lobo(rows)
    return {
        "schema": SCHEMA,
        "status": "retrospective_exploratory_12_previously_opened_physical_bearings_only",
        "pinned_previous_study_run": BASELINE_PRIOR_RUN,
        "pinned_original_mat_audit_run": REAL_AUDIT_PRIOR_RUN,
        "historical_study_report_sha256": BASELINE_REPORT_SHA256,
        "historical_frozen_research_model_sha256": model["model_sha256"],
        "verified_original_measurement_count": provenance["source_recordings"],
        "verified_original_unique_signal_count": provenance["unique_recordings"],
        "physical_healthy_bearing_count": 6,
        "physical_damaged_bearing_count": 6,
        "all_bearings_were_previously_opened": True,
        "study": study,
        "independent_new_bearings_tested": 0,
        "new_prospective_healthy_specificity_measured": False,
        "production_accuracy_or_false_alarm_rate_established": False,
        "physical_si_calibration_verified": False,
        "research_only_noncommercial_data": True,
        "production_ml_activation_allowed": False,
        "model_exported_or_approved": False,
        "paid_deepseek_request_performed": False,
        "notice": "사후 분석: 전체 12개 베어링은 과거 연구에서 이미 열어 본 자료입니다. "
                  "LOBO 점수 및 구간은 탐색적 설명이며 새로운 독립 평가나 현장 정확도는 아닙니다.",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features-dir", type=Path, required=True)
    ap.add_argument("--audits-dir", type=Path, required=True)
    ap.add_argument("--previous-report", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        report = evaluate_historical_artifacts(
            args.features_dir, args.audits_dir, args.previous_report)
        if args.out.exists() or args.out.is_symlink():
            raise SourceAuditError("refuse_overwriting_previous_evaluation")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(json.dumps({
            "status": report["status"],
            "matrix": report["study"]["metrics"]["confusion_matrix"],
            "healthy_spec_descriptive": report["study"]["descriptive_healthy_specificity"],
            "sensitivity_descriptive": report["study"]["descriptive_damage_sensitivity"],
            "new_independent_healthy_test": False,
            "production_activation": False,
        }, ensure_ascii=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print("RETROSPECTIVE_ML_BLOCKED:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
