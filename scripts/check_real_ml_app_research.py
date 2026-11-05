"""CI-only independent comparison: original-RAR research CLI score == app ML.

Do NOT use this to claim an independent validation set: K001 was trained on.
Only verifies technical end-to-end signal/model/UI API inference plumbing.
Never uploads or logs raw signal/individual feature vectors.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from faultmate.app import app
from faultmate.integration.ml import load_validated_model
from scripts.extract_unseen_paderborn_damaged import PINNED_MODEL_SHA


def check(feature_path: Path, score_path: Path) -> dict:
    raw = feature_path.read_bytes()
    previously = json.loads(score_path.read_text(encoding="utf-8"))
    if (
        len(raw) > 512000
        or previously.get("source_archive_verified_from_original_bytes_same_run") is not True
        or previously.get("source_mat_files_actually_read_this_run") != 80
        or previously.get("frozen_model_sha256") != PINNED_MODEL_SHA
        or previously.get("runtime_ml_model_approved") is not False
        or previously.get("new_independent_test_bearing_claimed") is not False
    ):
        raise ValueError("not_valid_real_raw_source_research_score")
    with TestClient(app) as client:
        response = client.post(
            "/api/ml/experimental-unitless-report",
            content=raw, headers={"content-type": "application/json"})
        if response.status_code != 200:
            raise ValueError("research_api_http_error")
        r = response.json()
        original = client.post("/api/ml/inspect",
                               content=(
                                   b"asset_id,trial_id,source_id,vibration_rms_m_s2,"
                                   b"vibration_peak_m_s2,current_rms_a\n"
                                   b"K001,T1,paderborn-bearing-datacenter,1.0,2.0,0.5\n"
                               ),
                               headers={"content-type": "text/csv"}).json()
    if (
        r.get("status") != "experimental_unapproved"
        or r.get("research_inference_performed") is not True
        or r.get("input_recordings") != 80
        or r.get("experimental_predicted_label") != previously["experimental_predicted_label"]
        or r.get("experimental_damage_model_score") != previously["experimental_damage_model_score"]
        or r.get("source_archive_reverified_from_original_bytes_this_http_request") is not False
        or r.get("model_approved_for_runtime") is not False
        or r.get("new_healthy_specificity_measured") is not False
        or r.get("confirmed_fault") is not False
        or r.get("safe_to_work") is not False
        or original.get("status") != "unavailable"
        or original.get("inference_performed") is not False
        or load_validated_model() is not None
    ):
        raise ValueError("research_score_disagrees_with_original_or_safety_gate")
    return {
        "status": "real_source_80_mat_cli_to_research_http_api_same_score_pass",
        "original_80_mat_from_real_rar": True,
        "score_matches": True,
        "model_sha256": PINNED_MODEL_SHA,
        "training_bearing_demo_not_independent_test": True,
        "raw_mat_ever_uploaded": False,
        "source_provenance_reverified_by_json_upload": False,
        "production_ml_inference_unavailable": True,
        "real_world_accuracy_measured": False,
        "actual_paid_api_requests": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--features", required=True, type=Path)
    p.add_argument("--score", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        result = check(args.features, args.score)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print("REAL_RAW_SENSOR_TO_RESEARCH_API_MISMATCH_NO_APPROVAL",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
