"""Extract eight *new* naturally damaged Paderborn bearings for one-time evaluation.

This is an isolated research-only path for an already frozen model, not
training. All eight asset IDs, accelerated-life labels, original Zenodo MD5s
and the model SHA were pre-registered before any extraction. Raw MAT signals
are read only in temporary folders and never uploaded. Unitless feature
engineering is shared with the original 12-bearing training experiment.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_paderborn_assets import (
    OFFICIAL_CONDITIONS, SourceAuditError, archive_inventory, archive_md5,
)
from scripts.audit_paderborn_raw_recordings import raw_signal_fingerprint
from scripts.convert_mat_to_csv import CURRENT, VIBRATION, as_signal, choose, read_channels
from scripts.extract_paderborn_unitless import FEATURE_NAMES, SCHEMA, record_features

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/PADERBORN_UNSEEN_DAMAGED_EVALUATION_MANIFEST_20261105.json"
ORIGINAL_MODEL = ROOT / "docs/experiments/PADERBORN_BEARING_AGGREGATED_UNAPPROVED_20261105.json"
KNOWN_NEW_MD5 = {
    "KA15": "db518f97ba5bcaedb09c648a317431e0",
    "KA22": "7a16a5bc88d5fe1d83d169f88f0709e8",
    "KA30": "715c0cf7862a7ba83e7c6a6fb5c91a61",
    "KB24": "c60ce8867c824583540794ae00cce333",
    "KB27": "965dd4af26391d7def4638c8b31a87e7",
    "KI14": "13603834975435ca10eb08de6d1840dc",
    "KI17": "d1055fe5cc44948e5d3a39f2e0db9dbe",
    "KI21": "911ce3e37a86d258818e3e93274752a2",
}
PREVIOUS_DEV = {"K001", "K002", "K003", "K004", "K005",
                "KA04", "KA16", "KB23", "KI04", "KI16"}
PREVIOUS_OPENED = {"K006", "KI18"}
PINNED_MODEL_SHA = "84a7c059fa769d1b0e2bd0075ecba92bcd06ae24acf961e0ea2120d9d44a0ab0"


def sha256(path: Path) -> str:
    """Exact byte hash for BINARY original MAT (never normalize raw sensor data)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_sha256(path: Path) -> str:
    """Pin JSON file content equally on Windows checkout CRLF and Linux LF.

    This must NEVER be used for RAR, MAT or raw signals. Changing JSON field
    content still breaks the hardcoded SHA-256; only line endings are ignored.
    """
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def verified_manifest(path: Path = MANIFEST) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if (doc.get("version") != 1
        or doc.get("preregistered_before_download") is not True
        or doc.get("license") != "CC BY-NC 4.0"
        or doc.get("fixed_threshold") != 0.5
        or doc.get("original_model_sha256") != PINNED_MODEL_SHA
        or doc.get("historical_development_assets") is None
        or set(doc["historical_development_assets"]) != PREVIOUS_DEV
        or set(doc.get("historical_opened_holdout_assets", [])) != PREVIOUS_OPENED
        or set(doc.get("mandatory_conditions", [])) != OFFICIAL_CONDITIONS
        or doc.get("files_per_bearing") != 80
        or doc.get("primary_damaged_label_location") != "Lessmeier et al. (2016), Table 5"
        or not str(doc.get("primary_damaged_label_reference", "")).startswith("https://mb.uni-paderborn.de/")
        or doc.get("original_model_relative_path")
           != "docs/experiments/PADERBORN_BEARING_AGGREGATED_UNAPPROVED_20261105.json"):
        raise SourceAuditError("unseen_damage_manifest_contract_invalid")
    rows = doc.get("assets")
    if (not isinstance(rows, list) or len(rows) != 8
        or any(not isinstance(x, dict) for x in rows)):
        raise SourceAuditError("eight_primary_paper_damaged_assets_required")
    got = {x.get("id"): x.get("md5") for x in rows}
    if got != KNOWN_NEW_MD5 or len(got) != len(rows):
        raise SourceAuditError("official_new_archive_md5_or_ids_invalid")
    if any(x.get("label") != "damaged" or x.get("damage_origin") != "accelerated_lifetime"
           for x in rows):
        raise SourceAuditError("new_bearing_primary_labels_invalid")
    if set(got) & (PREVIOUS_DEV | PREVIOUS_OPENED):
        raise SourceAuditError("previously_opened_bearing_used_as_unseen")
    if not ORIGINAL_MODEL.is_file() or canonical_json_sha256(ORIGINAL_MODEL) != PINNED_MODEL_SHA:
        raise SourceAuditError("frozen_original_model_not_identical")
    return doc


def extract_unseen(archive: Path, asset: str, *, sevenzip: str,
                   manifest_path: Path = MANIFEST) -> dict:
    doc = verified_manifest(manifest_path)
    if asset not in KNOWN_NEW_MD5:
        raise SourceAuditError("bearing_not_preregistered_for_unseen_test")
    if (not archive.is_file() or archive.is_symlink()
        or archive.name.lower() != asset.lower() + ".rar"
        or archive.stat().st_size < 100_000_000
        or archive_md5(archive) != KNOWN_NEW_MD5[asset]):
        raise SourceAuditError("wrong_unseen_archive_or_official_md5")
    if subprocess.run([sevenzip, "t", str(archive)], capture_output=True,
                      check=False, timeout=240).returncode:
        raise SourceAuditError("unseen_archive_integrity_failed")
    listing = subprocess.run([sevenzip, "l", "-slt", "-ba", str(archive)],
                             capture_output=True, check=False, timeout=60)
    if listing.returncode:
        raise SourceAuditError("unseen_archive_listing_failed")
    text = listing.stdout.decode("utf-8", errors="replace")
    archive_inventory(text, asset)
    members: dict[str, list[str]] = defaultdict(list)
    for line in text.splitlines():
        if line.startswith("Path = "):
            member = line[7:].strip()
            members[member.replace("\\", "/").rsplit("/", 1)[-1]].append(member)
    records = []
    first = {}
    duplicates = []
    with tempfile.TemporaryDirectory(prefix="faultmate-unseen-original-") as t:
        for condition in sorted(OFFICIAL_CONDITIONS):
            for trial in range(1, 21):
                filename = f"{condition}_{asset}_{trial}.mat"
                candidates = members.get(filename, [])
                if len(candidates) != 1:
                    raise SourceAuditError("unseen_recording_missing_or_duplicated:" + filename)
                target = Path(t) / f"{condition}_{trial}"
                target.mkdir()
                done = subprocess.run(
                    [sevenzip, "e", "-y", f"-o{target}", str(archive), candidates[0]],
                    capture_output=True, timeout=90, check=False)
                if done.returncode:
                    raise SourceAuditError("unseen_mat_extract_failed:" + filename)
                mat = target / filename
                if not mat.is_file():
                    raise SourceAuditError("unseen_mat_not_extracted:" + filename)
                mat_sha = sha256(mat)
                channels = read_channels(mat)
                vib, cur = choose(channels, VIBRATION), choose(channels, CURRENT)
                vibration, current = as_signal(vib), as_signal(cur)
                fingerprint = raw_signal_fingerprint(vibration, current)
                prior = first.get(fingerprint)
                if prior:
                    duplicates.append({"recording": filename, "duplicate_of": prior})
                    values = None
                else:
                    first[fingerprint] = filename
                    values = record_features(vibration, current)
                records.append({
                    "recording": filename, "condition": condition, "trial": trial,
                    "source_mat_sha256": mat_sha,
                    "source_raw_signal_fingerprint": fingerprint,
                    "sample_count": int(vibration.size),
                    "duplicate_of": prior, "values": values,
                })
                mat.unlink()
    if len(records) != 80:
        raise SourceAuditError("unseen_80_mats_required")
    return {
        "schema": SCHEMA, "evaluation_role": "never_seen_damaged_only",
        "status": "real_original_unseen_damaged_features_unapproved",
        "source_model_sha256": PINNED_MODEL_SHA,
        "source_manifest_sha256": canonical_json_sha256(manifest_path),
        "label_source": "Lessmeier et al. (2016), Table 5",
        "bearing_id": asset, "label": "damaged",
        "damage_origin": "accelerated_lifetime",
        "license": "CC BY-NC 4.0",
        "archive_verified": True, "official_archive_md5": KNOWN_NEW_MD5[asset],
        "source_recording_count": 80, "unique_recording_count": len(first),
        "feature_names": list(FEATURE_NAMES),
        "raw_si_units_verified": False, "approved_for_runtime": False,
        "duplicates": duplicates, "records": records,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", required=True, type=Path)
    p.add_argument("--bearing-id", required=True)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--sevenzip")
    args = p.parse_args(argv)
    executable = args.sevenzip or shutil.which("7z") or shutil.which("7zz")
    if not executable and sys.platform == "win32":
        path = Path(r"C:\Program Files\7-Zip\7z.exe")
        if path.is_file():
            executable = str(path)
    try:
        if not executable:
            raise SourceAuditError("7zip_unavailable")
        report = extract_unseen(args.archive.absolute(), args.bearing_id.upper(),
                                sevenzip=executable)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        print(json.dumps({
            "source": "official_original_paderborn", "asset": report["bearing_id"],
            "checked_records": 80, "unique": report["unique_recording_count"],
            "duplicates": len(report["duplicates"]),
            "status": report["status"], "ml_model_changed": False,
        }))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print("UNSEEN_SOURCE_EXTRACTION_REJECTED_NO_REPORT:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
