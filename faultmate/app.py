"""FaultMate AI P2: read-only knowledge + local deterministic triage."""
from __future__ import annotations
from pathlib import Path
from fastapi import Request
from fastapi import FastAPI, HTTPException, Query, Response
from faultmate.diagnostics.engine import TriageRequest, available_options, triage
from faultmate.knowledge.repository import load_catalog, case_summaries, get_case
from faultmate.integration.context import ContextPreviewRequest, capabilities, evidence_preview
from faultmate.integration.agent import AgentReviewRequest, review as review_agent, configured as agent_configured
from faultmate.integration.ml import capabilities as ml_capabilities, inspect_csv, MAX_CSV_BYTES
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from faultmate.local_request_boundary import browser_request_allowed, REJECTION

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB = PROJECT_ROOT / "web"
app = FastAPI(title="FaultMate AI", version="0.7.2", docs_url=None, redoc_url=None, openapi_url=None)

@app.middleware("http")
async def local_browser_request_boundary(request: Request, call_next):
    """Reject DNS-rebinding Host and cross-origin POST before paid agent code.

    No cookies, tokens or browser secrets are stored. Local Python/CLI calls
    without Origin continue to work. The actual Windows launcher still binds
    127.0.0.1; this also protects static assets from a foreign Host header.
    """
    if not browser_request_allowed(request):
        return JSONResponse(
            status_code=403,
            content={"detail": REJECTION},
            headers={"Cache-Control": "no-store, private", "Pragma": "no-cache"},
        )
    return await call_next(request)


@app.get("/api/status")
def status():
    return {
        "api": "ok", "app": "FaultMate AI", "phase": "P2", "ui_release": "P7.2-Final",
        "diagnostic_engine": "deterministic_rules_unverified", "deepseek_agent": "not_connected",
        "ml_model": "validated_experimental_only" if ml_capabilities()["inference_enabled"] else "unvalidated",
        "external_transfer": False,
        "notice": "로컬 규칙 기반 원인 후보 검토용. 실제 원인 확정이나 설비 조작을 수행하지 않습니다.",
        "integration_contract": "1.0.0-agent-ml-read-only",
    }

@app.get("/api/scope")
def scope():
    return {
        "target": ["컨베이어", "모터", "센서"],
        "example": {"symptom": "컨베이어가 움직이지 않지만 모터에서 소리가 남", "status": "unverified_example"},
        "v1_workflow": ["증상 입력", "설비 매뉴얼 및 기록 조회", "원인 후보 및 근거", "안전 점검 조건 확인", "실제 확인 결과 반영"],
        "prohibited": ["설비 원격 제어", "인터록 우회", "검증되지 않은 원인 확정", "무단 외부 데이터 전송"],
    }

@app.get("/api/knowledge/overview")
def knowledge_overview():
    catalog = load_catalog()
    return {"schema_version": catalog["schema_version"], "case_count":len(catalog["cases"]),
            "source_count":len(catalog["sources"]), "stage":"P2",
            "diagnosis_available":True, "agent_ml_owner":"Antigravity",
            "notice":catalog["safety_policy"]["mandatory_notice"]}

@app.get("/api/knowledge/sources")
def knowledge_sources():
    return {"sources":load_catalog()["sources"]}

@app.get("/api/knowledge/cases")
def knowledge_cases(equipment: str | None = Query(default=None, max_length=20)):
    if equipment is not None and equipment not in ("컨베이어", "모터", "센서"):
        raise HTTPException(status_code=422, detail="unsupported equipment category")
    return {"cases":case_summaries(equipment)}

@app.get("/api/knowledge/cases/{case_id}")
def knowledge_case(case_id: str):
    if not 1 <= len(case_id) <= 32:
        raise HTTPException(status_code=404, detail="case not found")
    case = get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    return {"case":case}

@app.get("/api/diagnostics/options")
def diagnostics_options():
    return available_options()

@app.post("/api/diagnostics/evaluate")
def diagnostics_evaluate(payload: TriageRequest, response: Response):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    try:
        return triage(payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="case not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@app.get("/api/integration/capabilities")
def integration_capabilities():
    result = capabilities()
    result["agent"]["configured"] = agent_configured()
    result["ml"] = ml_capabilities()
    return result

@app.post("/api/integration/evidence-preview")
def integration_evidence_preview(payload: ContextPreviewRequest, response: Response):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    try:
        return evidence_preview(payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="case not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@app.post("/api/agent/review")
def agent_review(payload: AgentReviewRequest, response: Response):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    try:
        return review_agent(payload)
    except (LookupError,ValueError) as exc:
        raise HTTPException(status_code=422,detail=str(exc))

@app.post("/api/ml/inspect")
async def ml_inspect(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    if request.headers.get("content-type", "").split(";")[0].strip() != "text/csv":
        raise HTTPException(status_code=415, detail="text_csv_required")
    try:
        declared = int(request.headers.get("content-length", "0"))
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_content_length")
    if declared > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="csv_too_large")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_CSV_BYTES:
            raise HTTPException(status_code=413, detail="csv_too_large")
    return inspect_csv(bytes(data))


@app.post("/api/ml/experimental-original-rar")
async def experimental_original_rar(request: Request, response: Response):
    """Local, single-flight original RAR input -> 80 MAT -> frozen research ML."""
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    try:
        from faultmate.integration.research_raw_archive import inspect_original_rar
        return await inspect_original_rar(request)
    except (ImportError, ModuleNotFoundError):
        return {
            "status": "unavailable", "research_inference_performed": False,
            "confirmed_fault": False, "safe_to_work": False,
            "message": "원본 RAR 분석에 필요한 Python 연구용 의존성이 없습니다.",
        }


@app.post("/api/ml/experimental-unitless-report")
async def research_unitless_report(request: Request, response: Response):
    """Research-only scoring from 80 declared dimensionless source features.

    A JSON upload is UNTRUSTED: it is NOT cryptographic proof of source MAT
    files. Only the separate raw-RAR CLI independently checks original bytes.
    Never mutate, train, or approve models; keep /api/ml/inspect unchanged.
    """
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    limit = 512_000
    if request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
        raise HTTPException(status_code=415, detail="research_json_required")
    try:
        declared = int(request.headers.get("content-length", "0"))
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_content_length")
    if declared > limit:
        raise HTTPException(status_code=413, detail="research_report_too_large")
    raw = bytearray()
    async for piece in request.stream():
        raw.extend(piece)
        if len(raw) > limit:
            raise HTTPException(status_code=413, detail="research_report_too_large")
    if not raw:
        return {"status": "unsupported_input", "research_inference_performed": False,
                "confirmed_fault": False, "safe_to_work": False,
                "message": "실험용 특징 보고서가 비어 있습니다."}
    try:
        # Science dependencies are imported only for this explicit optional
        # research action, so existing rule-based diagnosis remains independent.
        from scripts.run_experimental_paderborn_ml import score_original_feature_report
        import json
        doc = json.loads(raw.decode("utf-8-sig"))
        result = score_original_feature_report(doc)
    except (ImportError, ModuleNotFoundError):
        return {"status": "unavailable", "research_inference_performed": False,
                "confirmed_fault": False, "safe_to_work": False,
                "message": "연구용 ML 의존성 설치가 완료되지 않았습니다."}
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            OverflowError):
        return {"status": "unsupported_input", "research_inference_performed": False,
                "confirmed_fault": False, "safe_to_work": False,
                "message": "검증 가능한 4조건×20회 진동·전류 특징 보고서가 아닙니다."}
    # The upload itself can be forged, even if source MD5 string and MAT SHA
    # strings MATCH a catalog. No API can reverify original raw RAR by JSON.
    return {
        "status": "experimental_unapproved",
        "research_inference_performed": True,
        "source_archive_reverified_from_original_bytes_this_http_request": False,
        "uploaded_metadata_is_original_provenance_proof": False,
        "result_may_be_from_previously_trained_bearing": True,
        "bearing_id": result["research_input_source"]["bearing_id"],
        "input_recordings": result["research_input_source"]["source_records"],
        "unique_signal_pairs_reported": result["research_input_source"]["unique_signal_pairs"],
        "experimental_predicted_label": result["experimental_predicted_label"],
        "experimental_damage_model_score": result["experimental_damage_model_score"],
        "frozen_model_sha256": result["frozen_model_sha256"],
        "model_approved_for_runtime": False,
        "new_healthy_specificity_measured": False,
        "field_accuracy_measured": False,
        "confirmed_fault": False,
        "safe_to_work": False,
        "ml_predictions_are_not_maintenance_authorization": True,
        "message": "기존 연구용 모델의 실험 점수입니다. 업로드된 JSON만으로 원본 측정 파일은 재검증되지 않습니다. 현장 고장 확정이나 정비 허가가 아닙니다.",
    }

app.mount("/assets", StaticFiles(directory=WEB), name="web-assets")

@app.get("/")
def index():
    return FileResponse(WEB / "index.html")
