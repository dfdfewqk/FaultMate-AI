"""No-network synthetic safety tests for eight NEW original-Paderborn assets.

Fake feature records exercise validation paths, not real classification results.
CI runs the actual original Zenodo RAR / 640 MAT path separately.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from scripts.audit_paderborn_assets import OFFICIAL_CONDITIONS
from scripts.extract_paderborn_unitless import FEATURE_NAMES, SCHEMA
from scripts.extract_unseen_paderborn_damaged import (
    KNOWN_NEW_MD5, MANIFEST, PINNED_MODEL_SHA, ORIGINAL_MODEL,
    verified_manifest, sha256, canonical_json_sha256,
)
from scripts.evaluate_unseen_paderborn_damaged import (
    frozen_coefficients, evaluate, verify_new_reports, _wilson_interval,
)


def _synthetic_source_files(tmp_path):
    directory = tmp_path / "fake_unseen"
    directory.mkdir()
    manifest = verified_manifest()
    for asset in sorted(KNOWN_NEW_MD5):
        rows = []
        for cond in sorted(OFFICIAL_CONDITIONS):
            for trial in range(1, 21):
                name = f"{cond}_{asset}_{trial}.mat"
                rows.append({
                    "recording": name, "condition": cond, "trial": trial,
                    "source_mat_sha256": hashlib.sha256((name + "MAT").encode()).hexdigest(),
                    "source_raw_signal_fingerprint": hashlib.sha256(name.encode()).hexdigest(),
                    "sample_count": 256000, "duplicate_of": None,
                    "values": [float(trial / 10 + idx + k / 3)
                               for k, idx in enumerate(range(12))],
                })
        doc = {
            "schema": SCHEMA,
            "evaluation_role": "never_seen_damaged_only",
            "status": "real_original_unseen_damaged_features_unapproved",
            "source_model_sha256": PINNED_MODEL_SHA,
            "source_manifest_sha256": sha256(MANIFEST),
            "label_source": "Lessmeier et al. (2016), Table 5",
            "bearing_id": asset, "label": "damaged",
            "damage_origin": "accelerated_lifetime", "license": "CC BY-NC 4.0",
            "archive_verified": True,
            "official_archive_md5": KNOWN_NEW_MD5[asset],
            "source_recording_count": 80, "unique_recording_count": 80,
            "feature_names": list(FEATURE_NAMES),
            "raw_si_units_verified": False, "approved_for_runtime": False,
            "duplicates": [], "records": rows,
        }
        (directory / f"{asset}.json").write_text(json.dumps(doc), encoding="utf-8")
    return directory


def test_predeclared_assets_are_new_and_from_primary_real_damage_table():
    doc = verified_manifest()
    assert set(KNOWN_NEW_MD5) == {row["id"] for row in doc["assets"]}
    assert all(a["label"] == "damaged" and
               a["damage_origin"] == "accelerated_lifetime" for a in doc["assets"])
    assert set(KNOWN_NEW_MD5).isdisjoint(doc["historical_development_assets"])
    assert set(KNOWN_NEW_MD5).isdisjoint(doc["historical_opened_holdout_assets"])
    assert "KA15" in KNOWN_NEW_MD5 and "KI21" in KNOWN_NEW_MD5


def test_model_is_fixed_unapproved_and_still_excludes_new_bearings():
    fixed = frozen_coefficients()
    assert len(fixed["coefs"]) == len(FEATURE_NAMES) == 12
    assert fixed["threshold"] == .5
    assert fixed["model_sha256"] == sha256(ORIGINAL_MODEL) == PINNED_MODEL_SHA
    model = json.loads(ORIGINAL_MODEL.read_text(encoding="utf-8"))
    assert model["approved_for_runtime"] is False
    assert model["runtime_inference_compatible"] is False
    assert model["source_numeric_si_units_verified"] is False
    assert set(model["training_asset_ids"]).isdisjoint(KNOWN_NEW_MD5)


def test_synthetic_fixture_exercises_all_eight_source_guards(tmp_path):
    data = _synthetic_source_files(tmp_path)
    signals, provenance = verify_new_reports(data)
    assert set(signals) == set(KNOWN_NEW_MD5)
    assert all(x.shape == (80, 12) for x in signals.values())
    assert provenance["source_mat_files"] == 640
    assert provenance["source_unique_signal_pairs"] == 640
    assert provenance["healthy_bearings"] == 0


def test_test_only_report_makes_no_accuracy_or_specificity_claim(tmp_path):
    data = _synthetic_source_files(tmp_path)
    r = evaluate(data)
    assert len(r["predictions"]) == 8
    assert r["damage_detected"] + r["damaged_missed"] == 8
    assert r["all_inputs_preregistered"] is True
    assert r["refitting_or_threshold_tuning_performed"] is False
    assert r["overall_accuracy_measured"] is False
    assert r["specificity_measured"] is False
    assert r["false_alarm_rate_measured"] is False
    assert r["production_model_approved"] is False
    assert r["model_activated"] is False
    assert r["field_generalization_proven"] is False
    lo, hi = r["wilson_95pct_interval_damaged_only"]
    assert 0 <= lo <= hi <= 1


def test_no_prior_healthy_holdout_or_extra_file_permitted(tmp_path):
    data = _synthetic_source_files(tmp_path)
    (data / "K006.json").write_text("{}")
    with pytest.raises(ValueError, match="exact_eight_unseen_reports"):
        verify_new_reports(data)


@pytest.mark.parametrize("field,new_value,error_text", [
    ("label", "healthy", "unseen_source_provenance_failed"),
    ("official_archive_md5", "0" * 32, "unseen_source_provenance_failed"),
    ("approved_for_runtime", True, "unseen_source_provenance_failed"),
])
def test_source_tamper_and_fabricated_approval_are_blocked(tmp_path, field,
                                                             new_value, error_text):
    data = _synthetic_source_files(tmp_path)
    f = data / "KA15.json"
    doc = json.loads(f.read_text())
    doc[field] = new_value
    f.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match=error_text):
        verify_new_reports(data)


def test_changed_original_mat_fingerprint_is_rejected(tmp_path):
    data = _synthetic_source_files(tmp_path)
    f = data / "KA15.json"
    doc = json.loads(f.read_text())
    doc["records"][3]["source_raw_signal_fingerprint"] = doc["records"][2][
        "source_raw_signal_fingerprint"]
    f.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="unseen_duplicate_order_or_identity_invalid"):
        verify_new_reports(data)


def test_incomplete_operating_condition_rejected(tmp_path):
    data = _synthetic_source_files(tmp_path)
    f = data / "KA15.json"
    doc = json.loads(f.read_text())
    doc["records"][0]["condition"] = "N15_M07_F10"
    f.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="unseen_original_recording_name_invalid"):
        verify_new_reports(data)


def test_wilson_interval_small_n_not_claim_of_certain_accuracy():
    low, high = _wilson_interval(8, 8)
    assert low < .70 and high == 1.0
    with pytest.raises(ValueError):
        _wilson_interval(9, 8)


def test_line_ending_only_differences_preserve_json_proof_but_not_binary_hash(tmp_path):
    lf = tmp_path / "unix.json"
    crlf = tmp_path / "windows.json"
    lf.write_bytes(b'{"model":1,\n"threshold":0.5}\n')
    crlf.write_bytes(b'{"model":1,\r\n"threshold":0.5}\r\n')
    assert canonical_json_sha256(lf) == canonical_json_sha256(crlf)
    assert sha256(lf) != sha256(crlf)
    modified = tmp_path / "tampered.json"
    modified.write_bytes(b'{"model":2,\r\n"threshold":0.5}\r\n')
    assert canonical_json_sha256(modified) != canonical_json_sha256(lf)
