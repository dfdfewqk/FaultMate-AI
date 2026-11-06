"""Inventory *locally acquired* official HUST raw files without inferring labels.

Use after downloading publisher HUST v3 originals yourself from
https://data.mendeley.com/datasets/cbv7jyx4p9/3 . This program never
downloads, unpacks, trains, scores, estimates health, activates models or
claims the raw files are author-authenticated. It only records actual local
file hashes and observable layout. A published link alone is NOT a byte check.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

SOURCE_URL = "https://data.mendeley.com/datasets/cbv7jyx4p9/3"
MAX_FILES = 2000
MAX_DEPTH = 10
ALLOWED = frozenset({".mat", ".rar", ".zip", ".7z"})
IGNORE = frozenset({".DS_Store", "Thumbs.db"})


class HUSTInventoryError(ValueError):
    pass


def local_hust_inventory(root: Path) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise HUSTInventoryError("source_directory_missing_or_symlink")
    prefix = root.resolve(strict=True)
    files = []
    sha_to_file = {}
    duplicates = []
    for p in sorted(root.rglob("*"), key=lambda x: str(x).casefold()):
        rel = p.relative_to(root)
        if len(rel.parts) > MAX_DEPTH or any(part in (".", "..") for part in rel.parts):
            raise HUSTInventoryError("unexpected_path_depth")
        if p.is_symlink():
            raise HUSTInventoryError("symlink_source_not_allowed")
        if p.is_dir():
            continue
        if not p.is_file():
            raise HUSTInventoryError("unexpected_source_node")
        if p.name in IGNORE:
            continue
        if p.suffix.lower() not in ALLOWED:
            # This audit is strictly for vibration originals. Images and
            # documentation are not counted as MAT sensor recordings.
            continue
        if len(files) >= MAX_FILES:
            raise HUSTInventoryError("too_many_source_files")
        if not p.resolve(strict=True).is_relative_to(prefix):
            raise HUSTInventoryError("source_file_escape")
        h = hashlib.sha256()
        with p.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                h.update(chunk)
        digest = h.hexdigest()
        relative = rel.as_posix()
        old = sha_to_file.get(digest)
        if old:
            duplicates.append({"same_file_sha256": digest, "first_path": old,
                               "duplicate_path": relative})
        else:
            sha_to_file[digest] = relative
        files.append({"relative_path": relative, "sha256_actual_local_bytes": digest,
                      "length_bytes": p.stat().st_size,
                      "extension": p.suffix.lower()})
    return {
        "schema": "faultmate_hust_actual_local_file_hash_inventory_v1",
        "candidate_publisher": SOURCE_URL,
        "publisher_version": 3,
        "status": "LOCAL_BYTES_CHECKED_NOT_AUTHOR_PROVENANCE",
        "files_checked": len(files),
        "mat_files_checked": sum(x["extension"] == ".mat" for x in files),
        "archive_files_checked": sum(x["extension"] != ".mat" for x in files),
        "duplicate_content_sha256": duplicates,
        "local_file_list": files,
        "publisher_authentication_of_bytes_completed": False,
        "physical_bearing_count_or_identity_verified": False,
        "healthy_damage_labels_verified": False,
        "numerical_signal_si_units_verified": False,
        "independent_healthy_validation_performed": False,
        "compatible_with_paderborn_12_feature_vibration_current_model": False,
        "production_ml_activation_allowed": False,
        "notice": (
            "로컬 파일 바이트의 SHA256만 계산했습니다. 저자의 원본 공개 목록과"
            "해시 대조, 각 물리 베어링 구분, 정상·손상 라벨은 별도 확인해야 합니다."
        ),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.out.exists() or a.out.is_symlink():
            raise HUSTInventoryError("cannot_overwrite_prior_inventory")
        report = local_hust_inventory(a.original_root)
        if report["files_checked"] == 0:
            raise HUSTInventoryError("no_supported_original_files")
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with a.out.open("x", encoding="utf-8") as f:
            f.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({
            "status": report["status"],
            "file_count": report["files_checked"],
            "mat_file_count": report["mat_files_checked"],
            "author_provenance_or_independent_validation": False,
            "production_model_approved": False,
        }, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print("HUST_LOCAL_INVENTORY_BLOCKED:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
