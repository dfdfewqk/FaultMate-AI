"""Synthetic-only tests for real HUST public publisher full 99-mat SHA run."""
import hashlib
import json

import pytest

from scripts import audit_hust_v3_all_official_mat_originals as audit
from scripts.verify_hust_official_public_original import PublicSourceError


def original_99_names():
    return sorted(
        f"{prefix}{kind}0{load}.mat"
        for prefix in ("N", "I", "O", "B", "IB", "IO", "OB")
        for kind in "45678"
        if not (kind == "4" and prefix in ("B", "IB"))
        for load in ("0", "2", "4")
    )


def fake_row(name):
    return {
        "name": name, "folder": "HUST bearing dataset",
        "sha256": hashlib.sha256(name.encode()).hexdigest(),
        "size": 6543210, "download_url": "https://data.mendeley.com/public-files/test",
    }


def shard_fixture(folder):
    filenames = original_99_names()
    assert len(filenames) == 99
    fingerprint = "a" * 64
    for shard in range(5):
        rows = []
        for i, name in enumerate(filenames):
            if i % 5 != shard:
                continue
            m = audit.NAME.fullmatch(name)
            digest = hashlib.sha256(name.encode()).hexdigest()
            rows.append({
                "original_name": name, "publisher_sha256": digest,
                "actual_bytes_sha256": digest, "publisher_byte_count": 6543210,
                "actual_byte_count": 6543210,
                "observed_vibration_samples": 512000,
                "file_name_fault_code": m["fault"],
                "file_name_bearing_type_code": m["type"],
                "file_name_load_code": m["load"],
                "publisher_sha_and_actual_bytes_match": True,
            })
        (folder / f"shard-{shard}.json").write_text(json.dumps({
            "schema": audit.SCHEMA, "source_id": audit.DATASET,
            "source_version": audit.VERSION, "shard_count": 5,
            "shard_index": shard, "original_count_in_first_party_index": 99,
            "first_party_index_sha256": fingerprint, "records": rows,
            "production_ml_approved": False,
            "original_raw_signals_stored_in_artifacts": False,
        }), encoding="utf-8")


def test_article_filename_contract_and_99_shards(monkeypatch):
    rows = [fake_row(name) for name in original_99_names()]
    monkeypatch.setattr(audit, "published_files", lambda: rows)
    index, publisher_sha = audit.official_mat_index()
    assert len(index) == 99
    assert len(publisher_sha) == 64
    assert sum(x["name"].startswith("N") for x in index) == 15


def test_merge_is_only_source_audit_and_warns_about_five_normal_codes(tmp_path):
    shard_fixture(tmp_path)
    report = audit.merge_shards(tmp_path)
    assert report["real_original_mat_files_checked"] == 99
    assert report["all_original_bytes_match_first_party_file_sha256"] is True
    assert report["observed_normal_code_count"] == 5
    assert report["original_paper_reported_healthy_physical_prototypes"] == 3
    assert report["naming_vs_paper_healthy_specimen_count_requires_author_confirmation"] is True
    assert report["actual_independent_healthy_physical_specimens_verified"] == 0
    assert report["fixed_paderborn_12_feature_vibration_current_model_compatible"] is False
    assert report["model_activation_allowed"] is False
    assert len(report["individual_sha256_results"]) == 99


def test_missing_shard_fails_closed(tmp_path):
    shard_fixture(tmp_path)
    (tmp_path / "shard-4.json").unlink()
    with pytest.raises(PublicSourceError, match="not_all_five"):
        audit.merge_shards(tmp_path)


def test_conflicting_shard_source_index_fails(tmp_path):
    shard_fixture(tmp_path)
    p = tmp_path / "shard-3.json"
    r = json.loads(p.read_text())
    r["first_party_index_sha256"] = "b" * 64
    p.write_text(json.dumps(r), encoding="utf-8")
    with pytest.raises(PublicSourceError, match="publisher_original_shard_evidence_mismatch"):
        audit.merge_shards(tmp_path)


def test_fabricated_approved_model_is_rejected(tmp_path):
    shard_fixture(tmp_path)
    p = tmp_path / "shard-2.json"
    r = json.loads(p.read_text())
    r["production_ml_approved"] = True
    p.write_text(json.dumps(r), encoding="utf-8")
    with pytest.raises(PublicSourceError, match="publisher_original_shard_evidence_mismatch"):
        audit.merge_shards(tmp_path)


def test_changed_file_sha_is_rejected(tmp_path):
    shard_fixture(tmp_path)
    p = tmp_path / "shard-2.json"
    r = json.loads(p.read_text())
    r["records"][0]["actual_bytes_sha256"] = "0" * 64
    p.write_text(json.dumps(r), encoding="utf-8")
    with pytest.raises(PublicSourceError, match="source_shards_incomplete_or_corrupt"):
        audit.merge_shards(tmp_path)


def test_per_file_duplicate_metadata_refused(monkeypatch):
    rows = [fake_row(name) for name in original_99_names()]
    rows[1]["sha256"] = rows[0]["sha256"]
    monkeypatch.setattr(audit, "published_files", lambda: rows)
    with pytest.raises(PublicSourceError, match="duplicate_name_or_source_sha"):
        audit.official_mat_index()


def test_all_source_filename_contamination_refused(monkeypatch):
    rows = [fake_row(name) for name in original_99_names()]
    rows[0]["name"] = "unapproved_4.mat"
    monkeypatch.setattr(audit, "published_files", lambda: rows)
    with pytest.raises(PublicSourceError, match="file_name_outside"):
        audit.official_mat_index()


def test_no_report_overwrite(tmp_path):
    existing = tmp_path / "report.json"
    existing.write_text("KEEP OLD DATA", encoding="utf-8")
    result = audit.main(["--merge-dir", str(tmp_path), "--out", str(existing)])
    assert result == 2
    assert existing.read_text(encoding="utf-8") == "KEEP OLD DATA"
