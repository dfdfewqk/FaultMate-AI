"""CI-only real original RAR -> app's direct research ML endpoint parity.

Stream the same already source-verified ORIGINAL K001 RAR that was downloaded
from official Zenodo by this job. Never package, upload GitHub artifacts or
print raw signal bytes. K001 is a TRAINING member, NOT new healthy specificity.
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

READ_CHUNK = 1024 * 1024


def chunks(path: Path):
    with path.open("rb") as src:
        while True:
            data = src.read(READ_CHUNK)
            if not data:
                break
            yield data


def inspect_real_source_via_local_http(archive: Path, earlier: Path) -> dict:
    expected = json.loads(earlier.read_text(encoding="utf-8"))
    if (
        archive.name != "K001.rar" or not archive.is_file()
        or archive.is_symlink() or archive.stat().st_size < 100_000_000
        or expected.get("source_archive_verified_from_original_bytes_same_run") is not True
        or expected.get("source_mat_files_actually_read_this_run") != 80
        or expected.get("experimental_predicted_label") not in ("healthy", "damaged")
        or expected.get("runtime_ml_model_approved") is not False
    ):
        raise ValueError("K001_original_source_or_prior_score_unverified")
    with TestClient(app) as client:
        response = client.post(
            "/api/ml/experimental-original-rar",
            content=chunks(archive),
            headers={
                "content-type": "application/octet-stream",
                "x-faultmate-bearing-id": "K001",
            },
        )
    if response.status_code != 200:
        raise ValueError("raw_original_http_rejected")
    actual = response.json()
    if any((
        actual.get("status") != "experimental_unapproved",
        actual.get("research_inference_performed") is not True,
        actual.get("original_rar_md5_verified_in_this_request") is not True,
        actual.get("source_archive_reverified_from_original_bytes_this_http_request") is not True,
        actual.get("source_mat_files_actually_read_this_run") != 80,
        actual.get("source_original_recordings") != 80,
        actual.get("bearing_id") != "K001",
        actual.get("frozen_model_sha256") != expected.get("frozen_model_sha256"),
        actual.get("experimental_predicted_label") != expected["experimental_predicted_label"],
        actual.get("experimental_damage_model_score") != expected["experimental_damage_model_score"],
        actual.get("model_approved_for_runtime") is not False,
        actual.get("new_independent_healthy_specificity_measured") is not False,
        actual.get("overall_field_accuracy_measured") is not False,
        actual.get("confirmed_fault") is not False,
        actual.get("safe_to_work") is not False,
        actual.get("external_ai_transfer") is not False,
        load_validated_model() is not None,
    )):
        raise ValueError("real_original_http_vs_prior_offline_research_score_mismatch")
    return {
        "status": "REAL_ORIGINAL_PADERBORN_80_MAT_DIRECT_RAR_APP_SCORE_MATCH",
        "real_original_k001_rar_md5_verified_in_both_paths": True,
        "real_original_mat_records": 80,
        "real_frozen_model_score_matches": True,
        "previously_trained_k001_not_an_independent_test": True,
        "new_normal_specificity_measured": False,
        "production_bearing_model_activated": False,
        "paid_provider_calls": 0,
        "raw_signals_logged_or_packaged": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--prior-score", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect_real_source_via_local_http(args.archive, args.prior_score)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        # Only fixed non-sensitive error text, never leak original path or
        # source details from raw extractor into CI output.
        print("REAL_ORIGINAL_RAR_LOCAL_API_CHECK_FAILED_NO_FIELD_APPROVAL",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
