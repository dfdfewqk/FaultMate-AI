"""Stage7 localhost/browser boundary regression: no real paid DeepSeek calls."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from faultmate.app import app
from faultmate.integration import agent
from faultmate.local_request_boundary import (
    REJECTION, verified_local_host, verified_same_origin,
)

TRIAGE = {
    "case_id": "CONV-001", "equipment": "컨베이어",
    "emergency_hazard": "no",
    "observations": {"visible_jam": "yes"},
    "symptom_text": "LOCAL_ONLY_USER_INPUT_NEVER_SENT",
}


@pytest.mark.parametrize("value", [
    "127.0.0.1", "localhost", "LOCALHOST:8787", "127.0.0.1:8787",
    "testserver", "testserver:12345",
])
def test_allow_only_supported_loopback_host_literals(value):
    assert verified_local_host(value) is True


@pytest.mark.parametrize("value", [
    None, "", " ", "evil.example", "127.0.0.1.evil.example",
    "localhost.attacker.tld:8787", "localhost@evil.example",
    "evil.example@localhost", "127.0.0.2", "0.0.0.0",
    "127.0.0.1:0", "localhost:65536", "127.0.0.1:8787:50",
    "http://localhost:8787", "localhost:8787/path", "localhost:8787?x=1",
    "local host", "localhost\nignored",
])
def test_reject_rebound_dns_nonlocal_host_or_host_header_injection(value):
    assert verified_local_host(value) is False


@pytest.mark.parametrize("origin", [
    "null", "", "https://testserver",
    "http://evil.example", "http://testserver.evil.example",
    "http://testserver:443", "http://localhost",
    "http://testserver:8787",
    "http://testserver/path", "http://testserver/",
    "http://testserver?x=1", "http://testserver#token",
    "http://u:p@testserver", "http://testserver http://evil.example",
])
def test_api_rejects_nonidentical_or_malformed_origin(origin):
    assert verified_same_origin(origin, "testserver", "http") is False


def test_missing_origin_allowed_for_native_local_cli_only():
    assert verified_same_origin(None, "127.0.0.1:8787", "http") is True
    assert verified_same_origin("http://127.0.0.1:8787",
                                "127.0.0.1:8787", "http") is True
    assert verified_same_origin("http://LOCALHOST:8787",
                                "localhost:8787", "http") is True


@pytest.mark.parametrize("endpoint,method", [
    ("/", "get"),
    ("/assets/app.js", "get"),
    ("/api/status", "get"),
    ("/api/integration/evidence-preview", "post"),
    ("/api/agent/review", "post"),
    ("/api/ml/inspect", "post"),
])
def test_dns_rebinding_host_cannot_access_even_read_only_pages(endpoint, method):
    with TestClient(app) as client:
        kw = {"headers": {"host": "attacker.example:8787"}}
        if method == "post":
            kw["content"] = "{}"
        response = getattr(client, method)(endpoint, **kw)
    assert response.status_code == 403
    assert response.json() == {"detail": REJECTION}
    assert "no-store" in response.headers["cache-control"]


@pytest.mark.parametrize("header", [
    {"origin": "http://attacker.example"},
    {"origin": "null"},
    {"origin": "http://testserver.attacker.example"},
    {"origin": "https://testserver"},
    {"sec-fetch-site": "cross-site"},
    {"origin": "http://testserver", "sec-fetch-site": "cross-site"},
])
def test_browser_cross_site_paid_agent_request_never_reaches_provider(
        monkeypatch, header):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SYNTHETIC_TEST_KEY_NO_BILLING")
    monkeypatch.setattr(agent, "_invoke_deepseek",
                        lambda *_: pytest.fail("blocked cross-origin request reached agent"))
    with TestClient(app) as client:
        preview = client.post("/api/integration/evidence-preview",
                              json={"triage": TRIAGE}).json()
        assert len(preview["context_sha256"]) == 64
        body = {"triage": TRIAGE, "consent": True,
                "context_sha256": preview["context_sha256"]}
        response = client.post("/api/agent/review", json=body, headers=header)
    assert response.status_code == 403
    assert response.json()["detail"] == REJECTION


def test_cross_site_preview_and_diagnosis_post_also_blocked():
    with TestClient(app) as client:
        for path in ("/api/integration/evidence-preview",
                     "/api/diagnostics/evaluate"):
            r = client.post(path, json={"triage": TRIAGE},
                            headers={"origin": "http://attacker.example"})
            assert r.status_code == 403


@pytest.mark.parametrize("host,origin", [
    ("testserver", "http://testserver"),
    ("127.0.0.1:8787", "http://127.0.0.1:8787"),
    ("localhost:8787", "http://localhost:8787"),
])
def test_existing_normal_same_origin_browser_flow_remains_functional(
        monkeypatch, host, origin):
    calls = []

    def stub_local_only(context, key):
        calls.append({"context": context, "key": key})
        return {"candidate_order": [0], "question_indices": [0]}

    monkeypatch.setenv("DEEPSEEK_API_KEY", "SYNTHETIC_LOCAL_ONLY")
    monkeypatch.setattr(agent, "_invoke_deepseek", stub_local_only)
    h = {"host": host, "origin": origin, "sec-fetch-site": "same-origin"}
    with TestClient(app) as client:
        pre = client.post("/api/integration/evidence-preview",
                          json={"triage": TRIAGE}, headers=h)
        assert pre.status_code == 200
        digest = pre.json()["context_sha256"]
        review = client.post("/api/agent/review",
                             json={"triage": TRIAGE, "consent": True,
                                   "context_sha256": digest}, headers=h)
    assert review.status_code == 200
    result = review.json()
    assert result["status"] == "reviewed"
    assert len(calls) == 1
    assert calls[0]["key"] == "SYNTHETIC_LOCAL_ONLY"
    assert calls[0]["context"]["case_id"] == "CONV-001"
    assert result["confirmed_fault"] is False
    assert result["safe_to_work"] is False


def test_caller_without_origin_still_works_for_native_local_python():
    with TestClient(app) as client:
        r = client.get("/api/status")
        assert r.status_code == 200
        assert r.json()["ui_release"] == "P7.2-Final"
        d = client.post("/api/diagnostics/evaluate", json=TRIAGE)
        assert d.status_code == 200
        assert d.json()["state"] == "candidate_review"


def test_different_origin_with_correct_canonical_digest_still_blocked(
        monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SYNTHETIC_DO_NOT_SEND")
    monkeypatch.setattr(agent, "_invoke_deepseek",
                        lambda *_: pytest.fail("never call external AI"))
    with TestClient(app) as client:
        p = client.post("/api/integration/evidence-preview",
                        json={"triage": TRIAGE}).json()
        assert p["context_sha256"]
        response = client.post(
            "/api/agent/review",
            json={"triage": TRIAGE, "consent": True,
                  "context_sha256": p["context_sha256"]},
            headers={"origin": "http://other-localhost.example",
                     "sec-fetch-site": "cross-site"},
        )
        assert response.status_code == 403
