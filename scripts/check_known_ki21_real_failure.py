"""Verify a REAL historically tested KI21 failure at the local app boundary.

Original source RAR is downloaded by GitHub Actions from an existing public
Zenodo original-archive mirror into disposable runner storage. This script
streams the original file to the same app endpoint that a user clicks, which
authenticates official MD5 and re-extracts all 80 original paired MAT signals.

KI21 ALREADY belonged to the previous eight-damaged-bearing evaluation:
it was physically damaged but the frozen model predicted healthy. A repeat
confirms software/safety behavior. It is NOT new independent accuracy/specificity
and MUST NOT trigger threshold tuning, runtime ML activation or field use.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from faultmate.app import app
from faultmate.integration.ml import load_validated_model
from scripts.extract_unseen_paderborn_damaged import (
    KNOWN_NEW_MD5, PINNED_MODEL_SHA, verified_manifest,
)
from scripts.audit_paderborn_assets import archive_md5

FILE_CHUNK = 1024 * 1024


def stream_archive(archive: Path):
    with archive.open("rb") as stream:
        while True:
            chunk = stream.read(FILE_CHUNK)
            if not chunk:
                return
            yield chunk


def replay_actual_ki21(archive: Path) -> dict:
    _ = verified_manifest()
    if (archive.name != "KI21.rar"
        or archive.is_symlink() or not archive.is_file()
        or not 100_000_000 <= archive.stat().st_size <= 768 * 1024 * 1024
        or archive_md5(archive) != KNOWN_NEW_MD5["KI21"]):
        raise ValueError("known_ki21_original_archive_md5_or_size_unverified")

    with TestClient(app) as client:
        response = client.post(
            "/api/ml/experimental-original-rar",
            content=stream_archive(archive),
            headers={
                "content-type": "application/octet-stream",
                "x-faultmate-bearing-id": "KI21",
            },
        )
        legacy = client.get("/api/integration/capabilities").json()
    if response.status_code != 200:
        raise ValueError("real_ki21_local_replay_http_failed")
    doc = response.json()
    if any((
        doc.get("status") != "experimental_unapproved",
        doc.get("research_inference_performed") is not True,
        doc.get("bearing_id") != "KI21",
        doc.get("source_known_research_truth_label") != "damaged",
        doc.get("experimental_predicted_label") != "healthy",
        doc.get("historical_known_damaged_false_negative") is not True,
        doc.get("previously_opened_damaged_test_replay_not_new_evaluation") is not True,
        doc.get("old_training_bearing_may_have_been_used") is not False,
        doc.get("source_mat_files_actually_read_this_run") != 80,
        doc.get("original_rar_md5_verified_in_this_request") is not True,
        doc.get("source_archive_reverified_from_original_bytes_this_http_request") is not True,
        doc.get("frozen_model_sha256") != PINNED_MODEL_SHA,
        not isinstance(doc.get("experimental_damage_model_score"), (float, int)),
        doc.get("experimental_damage_model_score", 2.0) >= .5,
        doc.get("new_independent_healthy_specificity_measured") is not False,
        doc.get("overall_field_accuracy_measured") is not False,
        doc.get("physical_si_units_verified") is not False,
        doc.get("model_approved_for_runtime") is not False,
        doc.get("confirmed_fault") is not False,
        doc.get("safe_to_work") is not False,
        doc.get("maintenance_action_authorized") is not False,
        doc.get("external_ai_transfer") is not False,
        "미탐" not in doc.get("message", ""),
        legacy["ml"]["inference_enabled"] is not False,
        load_validated_model() is not None,
    )):
        raise ValueError("real_known_ki21_miss_not_reproduced_or_safety_claim_wrong")

    return {
        "status": "KNOWN_KI21_REAL_DAMAGED_FALSE_NEGATIVE_REPLAY_CONFIRMED",
        "physical_source_label": "damaged",
        "frozen_model_prediction": "healthy",
        "experimental_damage_model_score": doc["experimental_damage_model_score"],
        "original_mat_records": 80,
        "rechecked_source_md5": True,
        "historical_test_replayed_not_new_independent_accuracy": True,
        "new_healthy_specificity_measured": False,
        "production_model_activated": False,
        "safe_to_operate_equipment": False,
        "paid_api_requests": 0,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        print(json.dumps(replay_actual_ki21(args.archive),
                         ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError):
        print("KNOWN_KI21_SOURCE_OR_SAFETY_REPLAY_FAILED_NO_RELEASE",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
