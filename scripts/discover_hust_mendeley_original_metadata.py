"""Discover ACTUAL public HUST v3 file metadata from official Mendeley Data API.

This does not download original signals, claim verified original hashes,
infer physical bearing IDs, train models, or permit Paderborn model scoring.
All endpoints and dataset version are fixed to the publisher source.
"""
from __future__ import annotations

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ORIGIN = "https://api.data.mendeley.com"
DATASET = "cbv7jyx4p9"
VERSION = "3"
MAX_BYTES = 6_000_000


def retrieve(path: str, params: dict | None = None):
    if not path.startswith("/datasets/") or "://" in path or ".." in path:
        raise ValueError("unexpected_mendeley_url")
    suffix = "?" + urlencode(params) if params else ""
    request = Request(ORIGIN + path + suffix, headers={
        "Accept": "application/json",
        "User-Agent": "FaultMate-Research-Metadata-Audit/1.0 (noncommercial source check)",
    })
    try:
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise ValueError("mendeley_metadata_http_status_" + str(response.status))
            payload = response.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                raise ValueError("mendeley_metadata_too_large")
            return json.loads(payload)
    except HTTPError as exc:
        raise ValueError("mendeley_metadata_http_" + str(exc.code)) from exc
    except URLError as exc:
        raise ValueError("mendeley_metadata_network_unreachable") from exc


def _summary(entry: dict):
    if not isinstance(entry, dict):
        raise ValueError("metadata_entry_not_object")
    return {
        "id": entry.get("id"),
        "name": entry.get("name") or entry.get("filename"),
        "folder_id": entry.get("folder_id"),
        "size_bytes": entry.get("size") or entry.get("size_bytes"),
        "sha256_hash": entry.get("sha256_hash"),
        "content_type": entry.get("content_type") or entry.get("mime_type"),
    }


def discover():
    pub = retrieve(f"/datasets/{DATASET}", {"version": VERSION})
    folders = retrieve(f"/datasets/publics/{DATASET}/folders", {"version": VERSION})
    if isinstance(folders, dict):
        folders = folders.get("results") or folders.get("folders") or []
    if not isinstance(folders, list):
        raise ValueError("unexpected_folder_listing_shape")
    seen_folder_ids = set()
    pending = [None]
    for folder in folders:
        if not isinstance(folder, dict):
            raise ValueError("invalid_folder_metadata")
        fid = folder.get("id")
        if isinstance(fid, str):
            if fid in seen_folder_ids:
                raise ValueError("duplicate_folder_id")
            seen_folder_ids.add(fid)
            pending.append(fid)
    outputs = []
    for parent in pending:
        offset = 0
        while True:
            params = {"version": VERSION, "$start": offset, "$limit": 100}
            if parent:
                params["folder_id"] = parent
            listing = retrieve(f"/datasets/publics/{DATASET}/files", params)
            if isinstance(listing, dict):
                listing = listing.get("results") or listing.get("files") or []
            if not isinstance(listing, list):
                raise ValueError("unexpected_file_listing_shape")
            for item in listing:
                x = _summary(item)
                x["listing_parent"] = parent
                outputs.append(x)
            offset += len(listing)
            if not listing or len(listing) < 100:
                break
            if offset > 10000:
                raise ValueError("unexpectedly_large_dataset_index")
    ids = [x["id"] for x in outputs]
    if len(ids) != len(set(ids)):
        # API may list all folders recursively at the root; duplicate listings
        # are not independent files and MUST NOT be counted separately.
        outputs = list({x["id"]: x for x in outputs}.values())
    return {
        "dataset_id": DATASET, "published_version": 3,
        "api_source": ORIGIN,
        "public_metadata_available": True,
        "dataset_metadata_fields": sorted(pub.keys()) if isinstance(pub, dict) else [],
        "published_title": pub.get("name") if isinstance(pub, dict) else None,
        "folder_count": len(folders),
        "folders": [{"id": f.get("id"), "name": f.get("name"),
                     "parent_id": f.get("parent_id")} for f in folders],
        "file_count_from_official_api": len(outputs),
        "files": outputs,
        "actual_original_signal_bytes_downloaded": False,
        "original_file_hashes_recomputed": False,
        "specimen_identity_or_label_verified": False,
        "independent_normal_performance_established": False,
        "paderborn_model_compatible": False,
        "production_ml_allowed": False,
    }


def main() -> int:
    try:
        result = discover()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["file_count_from_official_api"] == 0:
            print("MENDELEY_HUST_V3_NO_VISIBLE_FILE_RECORDS", file=sys.stderr)
            return 3
        return 0
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("MENDELEY_HUST_V3_OFFICIAL_METADATA_DISCOVERY_BLOCKED:", str(exc),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
