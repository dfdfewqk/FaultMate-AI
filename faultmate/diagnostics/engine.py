"""P2: conservative, stateless evidence triage based only on P1 catalogue.

Self-reported observations can change *review order* but never establish fault,
probability, safe-to-work permission, or machine control. No LLM/ML is used.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from faultmate.knowledge.repository import get_case, load_catalog, case_summaries

Answer = Literal["yes", "no", "unknown"]
Equipment = Literal["컨베이어", "모터", "센서"]

class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    equipment: Equipment | None = None
    case_id: str | None = Field(default=None, max_length=32, pattern=r"^[A-Z]+-[0-9]{3}$")
    symptom_text: str = Field(default="", max_length=500)
    alarm_text: str = Field(default="", max_length=120)
    model_name: str = Field(default="", max_length=120)
    observations: dict[str, Answer] = Field(default_factory=dict, max_length=12)
    emergency_hazard: Answer = "unknown"

# Every question is answered only from a preexisting log or safe, distant visual observation.
OBSERVATIONS = {
    "motor_rotates_log": "기존 로그나 안전한 원격 표시에서 모터 회전이 확인됐나요?",
    "overload_alarm_log": "기존 알람 로그에 과부하·트립 기록이 있나요?",
    "visible_jam": "위험 구역에 접근하지 않고 제품 적체·걸림이 관찰됐나요?",
    "belt_slip_log": "기존 로그·안전한 관찰에서 벨트 미끄러짐이 확인됐나요?",
    "start_command_absent_log": "기존 HMI 기록에 모터 운전 명령이 없었나요?",
    "lens_contamination_seen": "위험 구역 밖에서 광학면 오염이 관찰됐나요?",
    "sensor_alignment_suspected": "기존 외관 기록에서 센서·반사판 정렬 이상이 관찰됐나요?",
    "sensor_plc_mismatch_log": "기존 센서 출력 기록과 PLC 입력 기록이 불일치하나요?",
}

# Matching ID = explicit illustrative case chosen by the operator.
# Rules do not assert a physical cause; they only bring a documented candidate
# to the top of the list when a related observation is *self-reported yes*.
RULES = {
    "CONV-001": {
        "motor_rotates_log": [2],
        "overload_alarm_log": [0],
        "visible_jam": [0],
    },
    "CONV-002": {
        "motor_rotates_log": [0],
        "belt_slip_log": [0, 1],
        "visible_jam": [2],
    },
    "CONV-003": {
        "visible_jam": [0],
        "belt_slip_log": [1],
        "sensor_plc_mismatch_log": [2],
    },
    "MOTOR-001": {
        "start_command_absent_log": [0],
        "overload_alarm_log": [1],
        "visible_jam": [2],
    },
    "MOTOR-002": {
        "overload_alarm_log": [0],
        "visible_jam": [2],
    },
    "SENSOR-001": {
        "sensor_alignment_suspected": [0],
        "lens_contamination_seen": [1],
    },
    "SENSOR-002": {
        "lens_contamination_seen": [0],
        "sensor_alignment_suspected": [1],
        "sensor_plc_mismatch_log": [2],
    },
}

# Suggestions are always a request to choose a case, never an automatic diagnosis.
# Multiword phrases avoid generic one-token matches like "모터" or "센서".
SUGGESTION_PHRASES = {
    "CONV-001": ("모터 소리", "모터에서 소리", "모터 웅", "벨트가 움직이지", "이송이 안"),
    "CONV-002": ("벨트 미끄", "벨트 슬립", "모터 회전", "이송 불량"),
    "CONV-003": ("제품 걸림", "제품 적체", "컨베이어 간헐", "이송 걸림"),
    "MOTOR-001": ("모터 기동 불", "모터가 안 켜", "운전 명령에도", "모터 안 돌아"),
    "MOTOR-002": ("모터 과부하", "과부하 경보", "모터 트립"),
    "SENSOR-001": ("감지 못", "감지가 안", "제품 미감지", "센서 무반응"),
    "SENSOR-002": ("센서 오탐", "감지 흔들", "센서 간헐", "센서 오작동"),
}

NOTICE = "교육·검토용 원인 후보이며 실제 고장 진단·작업 허가가 아닙니다. 모델별 OEM 매뉴얼과 현장 안전절차가 우선합니다."
SAFETY_HOLD = "긴급 위험 징후가 보고되었습니다. 분석을 중단하고 현장 비상 대응 절차에 따라 즉시 책임자에게 알리세요. 설비에 접근하거나 임의 재가동하지 마세요."

def available_options():
    return {
        "equipment": ["컨베이어", "모터", "센서"],
        "cases": case_summaries(),
        "questions_by_case": {
            case_id: [{"id": key, "label": OBSERVATIONS[key]} for key in mapping]
            for case_id, mapping in RULES.items()
        },
        "answers": ["unknown", "yes", "no"],
        "notice": NOTICE,
    }

def suggestions(text: str, equipment: str | None):
    phrase = " ".join(text.lower().split())
    matches = []
    for entry in case_summaries(equipment):
        cid = entry["case_id"]
        hits = [p for p in SUGGESTION_PHRASES[cid] if p in phrase]
        if hits:
            matches.append((len(hits), entry))
    matches.sort(key=lambda item: (-item[0], item[1]["case_id"]))
    return [entry for _, entry in matches]

def triage(payload: TriageRequest):
    base = {
        "engine": "deterministic_p2", "external_transfer": False,
        "deepseek_used": False, "ml_used": False, "confirmed_fault": False,
        "safe_to_work": False, "stored": False, "notice": NOTICE,
    }
    if payload.emergency_hazard == "yes":
        return {**base, "state": "safety_hold", "message": SAFETY_HOLD,
                "candidate_causes": [], "next_questions": [], "sources": [], "suggested_cases": []}
    # The emergency path does not depend on diagnostic completeness or unknown data IDs.
    if set(payload.observations) - set(OBSERVATIONS):
        raise ValueError("unknown_observation_id")
    if payload.case_id is None and payload.observations:
        raise ValueError("case_required_for_observations")
    if not payload.case_id:
        return {**base, "state": "selection_required",
                "message": "증상과 가까운 사례를 직접 선택해 주세요. 자동으로 고장을 판정하지 않습니다.",
                "suggested_cases": suggestions(payload.symptom_text, payload.equipment),
                "candidate_causes": [], "next_questions": [], "sources": []}

    case = get_case(payload.case_id)
    if case is None:
        raise LookupError("case_not_found")
    if payload.equipment is not None and case["equipment"] != payload.equipment:
        raise ValueError("equipment_case_mismatch")
    allowed = set(RULES[case["case_id"]])
    if set(payload.observations) - allowed:
        raise ValueError("observation_not_applicable_to_case")

    sources = {s["id"]: s for s in load_catalog()["sources"]}
    used_sources = set()
    candidates = []
    for idx, entry in enumerate(case["candidate_causes"]):
        supporting = [OBSERVATIONS[key] for key, indices in RULES[case["case_id"]].items()
                      if idx in indices and payload.observations.get(key) == "yes"]
        used_sources.update(entry["source_ids"])
        candidates.append({
            "candidate": entry["candidate"], "why_to_consider": entry["why_to_consider"],
            "source_ids": entry["source_ids"], "not_confirmed": True,
            "review_group": "추가 확인 우선" if supporting else "일반 검토 후보",
            "reported_indicators": supporting,
            "rank_basis": "사용자가 선택한 관찰 항목(미검증)" if supporting else "P1 참고 자료",
            "_score": len(supporting), "_order": idx,
        })
    candidates.sort(key=lambda c: (-c["_score"], c["_order"]))
    for entry in candidates:
        del entry["_score"], entry["_order"]
    pending = [{"id": key, "question": OBSERVATIONS[key]}
               for key in RULES[case["case_id"]] if payload.observations.get(key, "unknown") == "unknown"]
    return {
        **base, "state": "candidate_review", "case_id": case["case_id"],
        "equipment": case["equipment"], "case_title": case["title"],
        "selection_basis": "작업자가 직접 선택한 교육용 사례 (자유 입력은 자동 검증되지 않음)",
        "symptom_text": payload.symptom_text,
        "alarm_text": payload.alarm_text,
        "model_name": payload.model_name,
        "message": "고장 원인을 확정하지 않았습니다. 확인된 현장 기록과 설비 모델이 일치하는지 검토하세요.",
        "candidate_causes": candidates,
        "next_questions": pending,
        "additional_information_questions": case["missing_evidence_questions"],
        "safe_existing_record_checks": case["observations"],
        "safety_gate": case["required_safety_gate"],
        "stop_escalation": case["stop_escalation"],
        "limitations": case["limitations"],
        "sources": [sources[sid] for sid in sorted(used_sources)],
        "suggested_cases": [],
    }
