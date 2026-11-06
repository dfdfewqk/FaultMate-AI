"""Re-run ORIGINAL previously opened damaged Paderborn bearings, NOT new tests.

Eight original real damaged physical bearings were already used to evaluate
this frozen model. This replays *the same* source and original fixed threshold
to verify app behavior on a known failure (KI21 was missed), not to generate
additional validation samples or to re-estimate sensitivity.

The original RAR is authenticated by the existing Paderborn official MD5,
then 7z integrity, original 80 dual-channel MATLAB recordings and 12 unitless
features from scripts.extract_unseen_paderborn_damaged.extract_unseen().
The model is the exact already frozen SHA-pinned logistic regression.

No model fitting, threshold change, paid API, runtime model approval, release,
or field operating/safety permission.
"""
from __future__ import annotations

from collections import defaultdict
import math
from pathlib import Path
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_paderborn_assets import OFFICIAL_CONDITIONS, SourceAuditError
from scripts.evaluate_unseen_paderborn_damaged import frozen_coefficients
from scripts.extract_paderborn_unitless import FEATURE_NAMES, SCHEMA
from scripts.extract_unseen_paderborn_damaged import (
    KNOWN_NEW_MD5, PINNED_MODEL_SHA, extract_unseen, verified_manifest,
)

SHA256_RE = re.compile(r"[a-f0-9]{64}\Z")
KNOWN_HISTORICAL_MISS = "KI21"


def validate_prior_damaged_report(doc: dict) -> tuple[np.ndarray, dict]:
    """Validate 80 original-trial feature records, NOT arbitrary 'new' assets.

    This function may also be unit-tested with SYNTHETIC JSON; only the
    run_prior_damaged_archive path revalidates real original RAR bytes.
    """
    manifest = verified_manifest()
    allowed = {r["id"]: r for r in manifest["assets"]}
    if not isinstance(doc, dict):
        raise SourceAuditError("historical_replay_feature_object_required")
    asset = doc.get("bearing_id")
    recorded = allowed.get(asset)
    if (recorded is None
        or doc.get("schema") != SCHEMA
        or doc.get("evaluation_role") != "never_seen_damaged_only"
        or doc.get("status") != "real_original_unseen_damaged_features_unapproved"
        or doc.get("source_model_sha256") != PINNED_MODEL_SHA
        or doc.get("label_source") != "Lessmeier et al. (2016), Table 5"
        or doc.get("label") != "damaged"
        or doc.get("damage_origin") != "accelerated_lifetime"
        or doc.get("license") != "CC BY-NC 4.0"
        or doc.get("official_archive_md5") != recorded["md5"]
        or doc.get("archive_verified") is not True
        or doc.get("raw_si_units_verified") is not False
        or doc.get("approved_for_runtime") is not False
        or doc.get("source_recording_count") != 80
        or doc.get("feature_names") != list(FEATURE_NAMES)):
        raise SourceAuditError("historically_opened_damaged_source_contract_mismatch")

    records = doc.get("records")
    if not isinstance(records, list) or len(records) != 80:
        raise SourceAuditError("damaged_replay_requires_80_mat_records")
    unique: list[list[float]] = []
    first: dict[str, str] = {}
    duplicates: list[dict] = []
    counts: dict[str, set[int]] = defaultdict(set)
    names: set[str] = set()
    for entry in records:
        if not isinstance(entry, dict):
            raise SourceAuditError("damaged_replay_record_object_required")
        cond, trial, name = (
            entry.get("condition"), entry.get("trial"), entry.get("recording")
        )
        if (cond not in OFFICIAL_CONDITIONS or type(trial) is not int
            or not 1 <= trial <= 20
            or name != f"{cond}_{asset}_{trial}.mat" or name in names):
            raise SourceAuditError("damaged_replay_condition_or_trial_invalid")
        names.add(name)
        counts[cond].add(trial)
        mat_sha = entry.get("source_mat_sha256")
        fingerprint = entry.get("source_raw_signal_fingerprint")
        if (not isinstance(mat_sha, str) or not SHA256_RE.fullmatch(mat_sha)
            or not isinstance(fingerprint, str)
            or not SHA256_RE.fullmatch(fingerprint)
            or type(entry.get("sample_count")) is not int
            or entry["sample_count"] < 16384):
            raise SourceAuditError("damaged_replay_mat_or_raw_fingerprint_invalid")
        previous = first.get(fingerprint)
        if entry.get("duplicate_of") != previous:
            raise SourceAuditError("damaged_replay_duplicate_record_mismatch")
        values = entry.get("values")
        if previous is None:
            first[fingerprint] = name
            if (not isinstance(values, list) or len(values) != len(FEATURE_NAMES)
                or any(type(x) not in (int, float) or not math.isfinite(x)
                       for x in values)):
                raise SourceAuditError("damaged_replay_invalid_12_unitless_features")
            unique.append([float(x) for x in values])
        else:
            if values is not None:
                raise SourceAuditError("damaged_replay_duplicate_counted_as_sample")
            duplicates.append({"recording": name, "duplicate_of": previous})
    if (set(counts) != OFFICIAL_CONDITIONS
        or any(ts != set(range(1, 21)) for ts in counts.values())
        or doc.get("duplicates") != duplicates
        or doc.get("unique_recording_count") != len(unique)
        or len(unique) < 60 or len(unique) + len(duplicates) != 80):
        raise SourceAuditError("damaged_replay_incomplete_source_or_duplicate_count")

    median = np.median(np.asarray(unique, dtype=float), axis=0)
    if median.shape != (len(FEATURE_NAMES),) or not np.all(np.isfinite(median)):
        raise SourceAuditError("damaged_replay_bad_aggregated_sensor_features")
    return median, {
        "bearing_id": asset,
        "physical_truth_label": "damaged",
        "source_mat_recordings": 80,
        "unique_signal_pairs": len(unique),
        "duplicates_excluded": len(duplicates),
    }


def score_prior_damaged_report(doc: dict) -> dict:
    vector, info = validate_prior_damaged_report(doc)
    frozen = frozen_coefficients()
    logit = float(np.dot((vector - frozen["mean"]) / frozen["scale"],
                         frozen["coefs"]) + frozen["intercept"])
    if not math.isfinite(logit):
        raise SourceAuditError("damaged_replay_nonfinite_logit")
    if logit >= 0:
        score = 1.0 / (1.0 + math.exp(-logit))
    else:
        e = math.exp(logit)
        score = e / (1.0 + e)
    label = "damaged" if score >= frozen["threshold"] else "healthy"
    miss = label == "healthy"
    if info["bearing_id"] == KNOWN_HISTORICAL_MISS and not miss:
        raise SourceAuditError("KI21_historical_false_negative_not_reproduced")
    return {
        "status": "historical_known_damaged_replay_not_new_test",
        "bearing_id": info["bearing_id"],
        "source_mat_recordings": info["source_mat_recordings"],
        "source_unique_signal_pairs": info["unique_signal_pairs"],
        "duplicates_excluded": info["duplicates_excluded"],
        "physical_truth_label": "damaged",
        "experimental_predicted_label": label,
        "experimental_damage_model_score": round(score, 8),
        "historical_false_negative": miss,
        "already_opened_in_previous_evaluation": True,
        "new_independent_damaged_or_healthy_test_performed": False,
        "independent_healthy_specificity_measured": False,
        "field_accuracy_measured": False,
        "field_safety_or_fault_confirmation": False,
        "model_runtime_approved": False,
        "frozen_model_sha256": frozen["model_sha256"],
        "retraining_or_threshold_adjustment": False,
        "source_data_license": "CC BY-NC 4.0",
    }


def run_prior_damaged_archive(
    archive: Path, bearing_id: str, *, sevenzip: str
) -> dict:
    """The sole route that authenticates original RAR + real 80 MAT bytes."""
    if bearing_id not in KNOWN_NEW_MD5:
        raise SourceAuditError("not_one_of_eight_previously_opened_damaged_assets")
    doc = extract_unseen(archive.absolute(), bearing_id, sevenzip=sevenzip)
    result = score_prior_damaged_report(doc)
    result["original_rar_md5_verified_in_this_run"] = True
    result["original_real_80_mat_rechecked_this_run"] = True
    return result
