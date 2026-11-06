"""HUST Hanoi 2023: download ONE publisher-listed N400.mat via Mendeley PUBLIC API.

Only a documented publicly accessible endpoint is used; no credentials,
login bypass, tokens, commercial model, DeepSeek or user data.
Publisher-provided SHA256 is REQUIRED and cross-checked against the local
original bytes. All original sample bytes remain on the ephemeral runner.
This is NOT proof of independent physical bearing count, sensor SI units,
a generalizable classifier, or the frozen Paderborn model's accuracy.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

DATASET = "cbv7jyx4p9"
VERSION = 3
URL_BASE = f"https://data.mendeley.com/public-api/datasets/{DATASET}"
FIXED_ORIGINAL_FILE = "N400.mat"
# Independently collected repository lockfile, NOT first-party author evidence.
CROSS_CHECK_SHA256 = "dd44b6d371c45c340c60034bfb554e2054e448b2ded39faf459bce6498ac174d"
MAX_INDEX = 1_000_000
MAX_SIGNAL = 20_000_000


class PublicSourceError(ValueError):
    pass


def _get_url(url: str, max_bytes: int) -> bytes:
    request = Request(url, headers={
        "User-Agent": "FaultMatePublicBearingSourceAudit/1.0",
        "Accept": "application/json, application/octet-stream;q=0.9",
    })
    try:
        with urlopen(request, timeout=55) as response:
            if response.status != 200:
                raise PublicSourceError("public_endpoint_unexpected_http_status")
            payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise PublicSourceError("public_original_exceeds_download_limit")
            return payload
    except HTTPError as exc:
        raise PublicSourceError(f"public_endpoint_http_{exc.code}") from exc
    except URLError as exc:
        raise PublicSourceError("public_endpoint_transport_failure") from exc


def _publisher_json(url: str):
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc != "data.mendeley.com"
        or not parts.path.startswith("/public-api/datasets/" + DATASET + "/")):
        raise PublicSourceError("publisher_api_origin_not_trusted")
    try:
        return json.loads(_get_url(url, MAX_INDEX))
    except (UnicodeError, ValueError) as exc:
        raise PublicSourceError("publisher_json_response_invalid") from exc


def published_files():
    folders = _publisher_json(f"{URL_BASE}/folders/{VERSION}")
    if not isinstance(folders, list):
        raise PublicSourceError("publisher_folder_index_invalid")
    parents = [("root", "root")]
    folder_ids = set()
    for item in folders:
        if not isinstance(item, dict):
            raise PublicSourceError("publisher_folder_entry_invalid")
        fid, name = item.get("id"), item.get("name")
        if (not isinstance(fid, str) or not fid or fid in folder_ids
            or not isinstance(name, str) or not name):
            raise PublicSourceError("publisher_folder_identity_invalid")
        folder_ids.add(fid)
        parents.append((fid, name))
    results = {}
    for fid, folder_name in parents:
        query = urlencode({"folder_id": fid, "version": VERSION})
        files = _publisher_json(f"{URL_BASE}/files?{query}")
        if not isinstance(files, list):
            raise PublicSourceError("publisher_file_index_invalid")
        for f in files:
            if not isinstance(f, dict):
                raise PublicSourceError("publisher_file_entry_invalid")
            filename, details = f.get("filename"), f.get("content_details")
            if (not isinstance(filename, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{2,80}\.(?:mat|png)", filename, flags=re.I)
                or not isinstance(details, dict)):
                raise PublicSourceError("publisher_original_name_or_metadata_invalid")
            digest, size, link = (details.get("sha256_hash"),
                                  details.get("size"), details.get("download_url"))
            if (not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or type(size) is not int or size <= 0
                or not isinstance(link, str)
                or urlsplit(link).scheme != "https"
                or not urlsplit(link).hostname):
                raise PublicSourceError("publisher_original_sha_or_download_missing")
            key = (folder_name, filename)
            if key in results:
                if results[key]["sha256"] != digest:
                    raise PublicSourceError("publisher_duplicate_file_conflict")
                continue
            results[key] = {
                "name": filename, "folder": folder_name,
                "size": size, "sha256": digest, "download_url": link,
            }
    return list(results.values())


def verify_one_official_original(items, downloader=_get_url):
    matches = [f for f in items if f["name"] == FIXED_ORIGINAL_FILE]
    if len(matches) != 1:
        raise PublicSourceError("publisher_fixed_original_not_uniquely_listed")
    info = matches[0]
    if info["sha256"] != CROSS_CHECK_SHA256:
        raise PublicSourceError("publisher_sha_differs_from_independent_archive_manifest")
    if info["size"] > MAX_SIGNAL:
        raise PublicSourceError("publisher_file_too_large_for_one_offline_probe")
    raw = downloader(info["download_url"], MAX_SIGNAL)
    if len(raw) != info["size"]:
        raise PublicSourceError("original_size_not_equal_to_official_index")
    if hashlib.sha256(raw).hexdigest() != info["sha256"]:
        raise PublicSourceError("actual_original_sha256_mismatch")
    # Parse the real MATLAB file, never assert original values are SI.
    from scipy.io import loadmat
    try:
        doc = loadmat(io.BytesIO(raw), squeeze_me=True, struct_as_record=False)
        import numpy as np
        vibration = np.asarray(doc["data"])
        if (vibration.size < 500_000 or not np.issubdtype(vibration.dtype, np.number)
            or not np.isfinite(vibration).all()):
            raise PublicSourceError("publisher_mat_signal_invalid")
        keys = sorted(k for k in doc if not k.startswith("__"))
    except (KeyError, TypeError, ValueError, NotImplementedError) as exc:
        raise PublicSourceError("publisher_mat_format_unrecognized") from exc
    return {
        "dataset_version": VERSION, "dataset_id": DATASET,
        "publisher_source_api": URL_BASE,
        "actual_original_file": FIXED_ORIGINAL_FILE,
        "actual_original_file_folder": info["folder"],
        "original_bytes_verified_to_first_party_sha256": True,
        "original_bytes_verified_to_independent_locked_sha256": True,
        "file_bytes": len(raw), "original_sha256": info["sha256"],
        "mat_numeric_sample_count": int(vibration.size),
        "mat_keys": keys,
        "first_party_file_metadata_count": len(items),
        "source_model": "HUST_HANOI_VIBRATION_ONLY",
        "producer_physical_asset_label_author_verified": False,
        "new_independent_normal_and_damaged_cohort_verified": False,
        "si_sensor_calibration_verified": False,
        "paderborn_vibration_current_model_compatible": False,
        "new_or_existing_model_trained_or_modified": False,
        "new_independent_specificity_measured": False,
        "production_model_activation_allowed": False,
        "paid_ai_api_called": False,
    }


def main():
    try:
        index = published_files()
        report = verify_one_official_original(index)
    except (PublicSourceError, OSError) as exc:
        print("HUST_PUBLIC_ORIGINAL_VERIFICATION_BLOCKED:", str(exc))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
