"""Verified structure for static reference cases; *not* a diagnostic decision engine."""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).with_name("catalog.json")

@lru_cache(maxsize=1)
def load_catalog():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    validate_catalog(data)
    return data

def validate_catalog(data):
    assert data.get("schema_version") == "1.0.0"
    assert data.get("project") == "FaultMate AI"
    sources = data.get("sources", [])
    cases = data.get("cases", [])
    source_ids = [s["id"] for s in sources]
    case_ids = [c["case_id"] for c in cases]
    if not sources or not cases or len(source_ids) != len(set(source_ids)) or len(case_ids) != len(set(case_ids)):
        raise ValueError("Empty or duplicated case/source identifiers")
    for s in sources:
        if not s["url"].startswith("https://") or not s.get("limit") or not s.get("evidence_scope"):
            raise ValueError("Source missing URL or scope/limitation")
    known = set(source_ids)
    for case in cases:
        if case.get("case_status") != "illustrative_evidence_map" or case.get("alarm_code") is not None:
            raise ValueError("Unverified case cannot claim confirmed fault or alarm code")
        if not case.get("required_safety_gate") or not case.get("missing_evidence_questions"):
            raise ValueError("Missing safety or evidence gate")
        if not case["observations"] or not case["candidate_causes"]:
            raise ValueError("Incomplete case")
        for entry in case["observations"] + case["candidate_causes"]:
            if not entry.get("source_ids") or not set(entry["source_ids"]).issubset(known):
                raise ValueError("Unknown or missing evidence reference")
        for cause in case["candidate_causes"]:
            if cause.get("not_confirmed") is not True:
                raise ValueError("Candidate must remain unconfirmed")
    return True

def case_summaries(equipment=None):
    data = load_catalog()
    cases = data["cases"]
    if equipment:
        cases = [c for c in cases if c["equipment"] == equipment]
    return [{"case_id":c["case_id"],"equipment":c["equipment"],"title":c["title"],"case_status":c["case_status"],"source_count":len({r for e in c["observations"] + c["candidate_causes"] for r in e["source_ids"]})} for c in cases]

def get_case(case_id):
    return next((c for c in load_catalog()["cases"] if c["case_id"] == case_id),None)
