"""Read-only explanation of the EXISTING frozen KI21 research prediction.

Genuine original KI21 archive -> verified original 80 MAT signals -> existing
12-feature per-bearing median -> exact linear logit feature contributions.
Explains only this frozen logistic model's arithmetic, not physical causation.
Known historical replay, NEVER a new independent test, retraining, or approval.
No original source files or user data are modified; output is stdout JSON.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from scripts.extract_paderborn_unitless import FEATURE_NAMES
from scripts.evaluate_unseen_paderborn_damaged import frozen_coefficients
from scripts.replay_prior_damaged_bearing import (
    KNOWN_HISTORICAL_MISS, score_prior_damaged_report,
    validate_prior_damaged_report,
)
from scripts.extract_unseen_paderborn_damaged import extract_unseen


def explain_frozen_logit(vector: np.ndarray, model: dict) -> dict:
    """Exact additive logistic terms; signed terms are not causal evidence."""
    values = np.asarray(vector, dtype=float)
    mean = np.asarray(model["mean"], dtype=float)
    scale = np.asarray(model["scale"], dtype=float)
    coef = np.asarray(model["coefs"], dtype=float)
    if (values.shape != (len(FEATURE_NAMES),)
            or mean.shape != values.shape
            or scale.shape != values.shape
            or coef.shape != values.shape
            or not np.all(np.isfinite(values))
            or not np.all(np.isfinite(mean))
            or not np.all(np.isfinite(scale))
            or np.any(scale <= 0)
            or not np.all(np.isfinite(coef))
            or not math.isfinite(float(model["intercept"]))):
        raise ValueError("invalid_frozen_feature_attribution_input")
    normalized = (values - mean) / scale
    contributions = normalized * coef
    logit = float(math.fsum([float(model["intercept"]), *map(float, contributions)]))
    if not math.isfinite(logit):
        raise ValueError("invalid_frozen_logit")
    probability = (1 / (1 + math.exp(-logit))) if logit >= 0 else (
        math.exp(logit) / (1 + math.exp(logit)))
    rows = [{
        "feature": name,
        "raw_dimensionless_value": float(x),
        "standardized_value": float(z),
        "frozen_coefficient": float(c),
        "signed_logit_contribution": float(term),
    } for name, x, z, c, term in zip(
        FEATURE_NAMES, values, normalized, coef, contributions)]
    rows.sort(key=lambda r: abs(r["signed_logit_contribution"]), reverse=True)
    return {
        "intercept": float(model["intercept"]),
        "logit": logit,
        "damage_model_score": probability,
        "fixed_threshold": float(model["threshold"]),
        "prediction": "damaged" if probability >= float(model["threshold"]) else "healthy",
        "features_sorted_by_absolute_logit_contribution": rows,
        "attribution_is_model_arithmetic_not_causal_fault_evidence": True,
    }


def analyze_ki21(archive: Path, *, sevenzip: str) -> dict:
    # This existing extractor checks the official archive MD5, complete
    # original 4x20 MAT signal sources, labels, SHA and duplicate records.
    doc = extract_unseen(archive.absolute(), KNOWN_HISTORICAL_MISS, sevenzip=sevenzip)
    vector, info = validate_prior_damaged_report(doc)
    previous = score_prior_damaged_report(doc)
    model = frozen_coefficients()
    explanation = explain_frozen_logit(vector, model)
    if (previous["experimental_predicted_label"] != explanation["prediction"]
        or abs(previous["experimental_damage_model_score"] -
               explanation["damage_model_score"]) > 0.000000011
        or previous["historical_false_negative"] is not True):
        raise ValueError("historical_ki21_attribution_not_reproduced")
    return {
        "status": "read_only_original_ki21_historical_false_negative_explanation",
        "bearing_id": KNOWN_HISTORICAL_MISS,
        "physical_truth_label": "damaged",
        "original_source_reauthenticated_this_run": True,
        "source_mat_recordings": info["source_mat_recordings"],
        "source_unique_signal_pairs": info["unique_signal_pairs"],
        "frozen_model_sha256": previous["frozen_model_sha256"],
        **explanation,
        "new_independent_test": False,
        "model_retrained_or_threshold_changed": False,
        "field_fault_cause_established": False,
        "independent_healthy_specificity_measured": False,
        "production_model_approved": False,
        "safe_to_work": False,
        "license": "CC BY-NC 4.0",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True,
                   help="Existing original KI21.rar; source remains untouched")
    p.add_argument("--sevenzip", default=None)
    args = p.parse_args()
    tool = args.sevenzip or shutil.which("7z") or shutil.which("7zz")
    if not tool:
        candidate = Path(r"C:\Program Files\7-Zip\7z.exe")
        if candidate.is_file():
            tool = str(candidate)
    if not tool:
        p.error("existing_7zip_required")
    result = analyze_ki21(args.archive, sevenzip=tool)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
