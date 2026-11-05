"""One-click LOCAL original RAR -> 80 MAT -> frozen research-only ML.

No server-side user-supplied file paths, no global source storage, no paid API.
Uploads stream to an exclusive temporary local file under an explicit cap;
source MD5, full archive inventory and the 80 original vibration/current MAT
recordings are checked AGAIN in this very request by the existing extractor.

The archived source remains CC BY-NC 4.0 and the original fitted ML is
NOT an approved production/field model. The HTTP response contains only
non-sensitive research metadata, not raw signals or full feature vectors.
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import tempfile
import threading
from pathlib import Path

from fastapi import HTTPException, Request
from scripts.audit_paderborn_assets import CATALOG, validate_catalog

MIN_ORIGINAL_RAR_BYTES = 100_000_000
MAX_ORIGINAL_RAR_BYTES = 768 * 1024 * 1024
MIN_EXTRA_DISK_BYTES = 256 * 1024 * 1024
READABLE_BEARING = re.compile(r"^[A-Z]{1,2}\d{2,3}$")
# Only one resource-intensive extraction at a time. No global job queue or
# background retained files; releases on success, validation failure, or error.
_RESEARCH_BUSY = threading.BoundedSemaphore(value=1)


def validate_bearing_id(raw_id: str | None) -> str:
    if not isinstance(raw_id, str) or not READABLE_BEARING.fullmatch(raw_id):
        raise HTTPException(status_code=422, detail="supported_original_bearing_id_required")
    if raw_id not in {a["id"] for a in validate_catalog(
        json.loads(CATALOG.read_text(encoding="utf-8"))
    )}:
        raise HTTPException(status_code=422, detail="only_original_paderborn_12_bearings_supported")
    return raw_id


def verify_rar_request(request: Request) -> tuple[str, int | None]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in ("application/octet-stream", "application/vnd.rar",
                            "application/x-rar-compressed"):
        raise HTTPException(status_code=415, detail="original_rar_binary_required")
    asset = validate_bearing_id(request.headers.get("x-faultmate-bearing-id"))
    header_size = request.headers.get("content-length")
    if header_size is None:
        return asset, None
    try:
        length = int(header_size)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid_archive_content_length") from exc
    if not 0 < length <= MAX_ORIGINAL_RAR_BYTES:
        raise HTTPException(
            status_code=413 if length > MAX_ORIGINAL_RAR_BYTES else 400,
            detail="original_rar_upload_length_invalid")
    return asset, length


def _research_score(archive: Path, asset: str) -> dict:
    # Runtime imports/load performed only in explicit research route. Uses
    # exactly the already established 12-feature scientific model and 0.5 cut.
    sevenzip = shutil.which("7z") or shutil.which("7zz")
    if not sevenzip:
        from sys import platform
        if platform == "win32":
            candidate = Path(r"C:\Program Files\7-Zip\7z.exe")
            if candidate.is_file():
                sevenzip = str(candidate)
    if not sevenzip:
        return {
            "status": "unavailable", "research_inference_performed": False,
            "confirmed_fault": False, "safe_to_work": False,
            "message": "원본 RAR을 읽는 7-Zip 실행 도구가 없어 분석을 시작하지 못했습니다.",
        }
    from scripts.run_experimental_paderborn_ml import run_archive
    score = run_archive(archive, asset, sevenzip=sevenzip)
    return {
        "status": "experimental_unapproved",
        "research_inference_performed": True,
        "original_rar_md5_verified_in_this_request": True,
        "source_archive_reverified_from_original_bytes_this_http_request": True,
        "source_mat_files_actually_read_this_run": score["source_mat_files_actually_read_this_run"],
        "four_paderborn_conditions_verified": score["research_input_source"]["four_source_conditions_present"],
        "bearing_id": asset,
        "source_original_recordings": score["research_input_source"]["source_records"],
        "source_unique_signal_pairs": score["research_input_source"]["unique_signal_pairs"],
        "duplicates_excluded": score["research_input_source"]["duplicates_excluded"],
        "frozen_model_sha256": score["frozen_model_sha256"],
        "experimental_predicted_label": score["experimental_predicted_label"],
        "experimental_damage_model_score": score["experimental_damage_model_score"],
        "old_training_bearing_may_have_been_used": True,
        "new_independent_healthy_specificity_measured": False,
        "overall_field_accuracy_measured": False,
        "physical_si_units_verified": False,
        "dataset_license": "CC BY-NC 4.0",
        "model_approved_for_runtime": False,
        "production_bearing_model_activated": False,
        "confirmed_fault": False,
        "safe_to_work": False,
        "maintenance_action_authorized": False,
        "external_ai_transfer": False,
        "message": (
            "원본 Paderborn RAR 및 80개 센서 측정파일을 실제 검증해 기존 연구 모델로 "
            "계산했습니다. 학습에 이미 사용한 베어링일 수 있으며 실제 현장 고장 확률이나 "
            "정비 허가가 아닙니다. 신규 독립 정상 베어링 오경보율은 미검증입니다."
        ),
    }


async def inspect_original_rar(request: Request) -> dict:
    """HTTP-only local stream; no filename/absolute path supplied by user."""
    asset, declared = verify_rar_request(request)
    if not _RESEARCH_BUSY.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="research_archive_scoring_already_running")
    try:
        with tempfile.TemporaryDirectory(prefix="faultmate-original-rar-only-") as tmp:
            root = Path(tmp)
            # Early disk guard. Original archive itself is retained only in
            # this temporary folder and unlinked when request exits.
            free = shutil.disk_usage(root).free
            if free < MIN_EXTRA_DISK_BYTES + (declared or MAX_ORIGINAL_RAR_BYTES):
                raise HTTPException(status_code=507, detail="insufficient_temporary_disk_for_original_rar")
            archive = root / f"{asset}.rar"
            size = 0
            with archive.open("xb") as out:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_ORIGINAL_RAR_BYTES:
                        raise HTTPException(status_code=413, detail="original_rar_exceeds_streaming_limit")
                    if chunk:
                        out.write(chunk)
            if not MIN_ORIGINAL_RAR_BYTES <= size <= MAX_ORIGINAL_RAR_BYTES:
                raise HTTPException(status_code=422, detail="original_rar_source_size_invalid")
            if declared is not None and declared != size:
                raise HTTPException(status_code=400, detail="original_rar_content_length_mismatch")
            # Use worker thread: browser and normal rule-based endpoints remain
            # responsive during expensive original MAT processing.
            try:
                # A browser abort/connection loss must NOT remove the temp RAR
                # and release the exclusive lock while the 7z thread still
                # reads it. Finish the read-only local check before cleanup.
                worker = asyncio.create_task(
                    asyncio.to_thread(_research_score, archive, asset))
                try:
                    return await asyncio.shield(worker)
                except asyncio.CancelledError:
                    await asyncio.shield(worker)
                    raise
            except (OSError, ValueError, TypeError, KeyError, RuntimeError,
                    ImportError, ModuleNotFoundError):
                # Do not echo temporary path, source bytes, archive exception
                # internals, or the original filename into browser/log output.
                return {
                    "status": "rejected_source",
                    "research_inference_performed": False,
                    "original_rar_md5_verified_in_this_request": False,
                    "confirmed_fault": False, "safe_to_work": False,
                    "message": (
                        "원저자 등록 MD5·압축 무결성·센서 채널·4조건×20회 또는 "
                        "고정 모델 검증에 실패했습니다. 예측하지 않았습니다."
                    ),
                }
    finally:
        _RESEARCH_BUSY.release()
