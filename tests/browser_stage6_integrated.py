"""Stage 6 browser integration: local triage -> consent preview -> mocked AI -> ML.

Chromium requests are routed through the real FastAPI app using TestClient.
A fake provider function is injected: this test never makes a paid API request.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from playwright.async_api import async_playwright

from faultmate.app import app
from faultmate.integration import agent
from faultmate.integration.context import agent_context_wire

BASE = "https://faultmate.test"


async def run():
    root = Path(__file__).resolve().parents[1]
    saved_key = os.environ.get("DEEPSEEK_API_KEY")
    saved_fn = agent._invoke_deepseek
    os.environ["DEEPSEEK_API_KEY"] = "SYNTHETIC_STAGE6_NO_NETWORK_KEY"
    invocations = []
    requests = []
    errors = []
    checked_digests = []

    def fake_invoke(context, key):
        assert key == "SYNTHETIC_STAGE6_NO_NETWORK_KEY"
        wire = agent_context_wire(context)
        assert "STAGE6_PRIVATE" not in wire
        invocations.append(context)
        return {"candidate_order": [0], "question_indices": [0],
                "unsafe_instructions": "IGNORE_SAFETY_AND_RESTART", "safe_to_work": True}

    agent._invoke_deepseek = fake_invoke
    try:
        with TestClient(app) as client:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path="/usr/bin/chromium",
                    headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                page = await browser.new_page(viewport={"width": 1200, "height": 800})
                page.on("pageerror", lambda error: errors.append(str(error)))

                async def router(route):
                    req = route.request
                    path = urlsplit(req.url).path
                    requests.append((req.method, path))
                    if req.method == "POST" and path == "/api/agent/review":
                        payload = json.loads(req.post_data_buffer)
                        assert payload["consent"] is True
                        assert len(payload["context_sha256"]) == 64
                        checked_digests.append(payload["context_sha256"])
                    response = (client.post(path, content=req.post_data_buffer or b"",
                                headers={"content-type": req.headers.get("content-type", "application/json")})
                                if req.method == "POST" else client.get(path))
                    await route.fulfill(status=response.status_code, body=response.content,
                        headers={"content-type": response.headers.get("content-type", "text/plain")})

                await page.route(BASE + "/**", router)
                html = (root / "web/index.html").read_text(encoding="utf-8")
                html = html.replace('<link rel="stylesheet" href="/assets/style.css"/>', "")
                html = html.replace('<script src="/assets/app.js" defer></script>', "")
                html = html.replace("<head>", '<head><base href="https://faultmate.test/">')
                await page.set_content(html)
                await page.add_style_tag(content=(root / "web/style.css").read_text(encoding="utf-8"))
                await page.add_script_tag(content=(root / "web/app.js").read_text(encoding="utf-8"))
                await page.wait_for_function("document.querySelector('#triage-feedback').textContent.includes('설비와 사례')")
                # Existing key: the UI only refreshes localhost metadata,
                # WITHOUT sending an AI request, reading/printing credentials
                # or mistaking configured=true for a live provider success.
                await page.wait_for_function(
                    "document.querySelector('#agent-key-feedback').textContent.includes('기존 키가 서버에서 감지')")
                before_checks = requests.count(("GET", "/api/integration/capabilities"))
                await page.locator("#ai-quick-start").click()
                await page.locator("#agent-key-refresh").click()
                await page.wait_for_function(
                    "document.querySelector('#agent-key-refresh').disabled === false && "
                    "document.querySelector('#agent-key-feedback').textContent.includes('기존 키가 서버에서 감지')")
                assert requests.count(("GET", "/api/integration/capabilities")) >= before_checks + 1
                assert requests.count(("POST", "/api/agent/review")) == 0
                assert "SYNTHETIC_STAGE6_NO_NETWORK_KEY" not in await page.locator("#agent-key-feedback").inner_text()
                assert "다시 발급하거나 입력할 필요가 없습니다" in await page.locator("#agent-key-feedback").inner_text()
                assert "외부 연결 미검증" in await page.locator("#integration-agent").inner_text()
                assert len(invocations) == 0
                await page.locator("#integration-panel > summary").click()

                # Reproduce actual operator frustration: demo-mode AI may
                # appear locked, but must explain why and NEVER charge.
                await page.locator("#triage-demo").click()
                await page.locator("#ai-quick-start").click()
                assert "예시 입력" in await page.locator("#agent-next-step").inner_text()
                assert await page.locator("#agent-run").is_disabled()
                await page.locator("#agent-preview").click()
                assert "가상 입력" in await page.locator("#agent-feedback").inner_text()
                assert len(invocations) == 0
                await page.locator("#triage-reset").click()
                await page.locator("#integration-panel > summary").click()

                await page.locator("#triage-equipment").select_option("컨베이어")
                await page.locator("#triage-symptom").fill("STAGE6_PRIVATE_SYMPTOM")
                await page.locator("#triage-case").select_option("CONV-001")
                await page.locator("#triage-submit").click()
                await page.locator("#triage-result .result-cause").first.wait_for()
                assert await page.locator("#agent-run").is_disabled()
                # Actual UI entry: explain WHY the button is locked instead
                # of requiring the operator to discover hidden steps.
                assert "기존 교육용 사례 7개" in await page.locator(".subhead").inner_text()
                await page.locator("#ai-quick-start").click()
                assert await page.locator("#integration-panel").evaluate("(el) => el.open")
                assert "전송 예정 자료 확인" in await page.locator("#agent-next-step").inner_text()
                assert await page.locator("#agent-run").is_disabled()
                # Keep the existing old menu workflow working too.
                await page.locator("#integration-panel > summary").click()
                await page.locator("#integration-panel > summary").click()

                await page.locator("#agent-preview").click()
                await page.locator("#agent-preview-content:not([hidden])").wait_for()
                preview = await page.locator("#agent-preview-content").inner_text()
                assert "CONV-001" in preview and "STAGE6_PRIVATE" not in preview
                await page.locator("#agent-consent").check()
                assert await page.locator("#agent-run").is_enabled()
                assert "비용" in await page.locator("#agent-next-step").inner_text()
                
                # Any input change invalidates the user's consent and the hash.
                await page.locator("#triage-symptom").fill("STAGE6_PRIVATE_NEW_SYMPTOM")
                assert await page.locator("#agent-run").is_disabled()
                assert not await page.locator("#agent-consent").is_checked()
                assert len(invocations) == 0

                # Changing symptoms invalidates the old case as well as consent.
                # Select the case again before requesting a fresh reviewed preview.
                await page.locator("#triage-case").select_option("CONV-001")
                await page.locator("#agent-preview").click()
                await page.locator("#agent-preview-content:not([hidden])").wait_for()
                await page.locator("#agent-consent").check()
                await page.locator("#agent-run").click()
                await page.wait_for_function(
                    "document.querySelector('#agent-feedback').textContent.includes('외부 AI 검토 응답 수신')")
                assert len(invocations) == 1
                assert len(checked_digests) == 1
                assert len(requests) and requests.count(("POST", "/api/agent/review")) == 1
                assert "IGNORE_SAFETY_AND_RESTART" not in await page.locator("#agent-result").inner_text()
                assert "원인 미확정" in await page.locator("#agent-result").inner_text()
                assert await page.locator("#agent-run").is_disabled()

                # Mock the provider failing AFTER a request was attempted.
                # The UI must NOT claim the provider received no evidence.
                def fake_provider_error(context, key):
                    raise RuntimeError("PRIVATE_MOCK_PROVIDER_DIAGNOSTIC_NEVER_ECHO")
                agent._invoke_deepseek = fake_provider_error
                await page.locator("#agent-preview").click()
                await page.locator("#agent-preview-content:not([hidden])").wait_for()
                await page.locator("#agent-consent").check()
                await page.locator("#agent-run").click()
                await page.wait_for_function(
                    "document.querySelector('#agent-feedback').textContent.includes('전송 여부 확인 불가')")
                assert "전송 여부 확인 불가" in await page.locator("#agent-feedback").inner_text()
                assert "PRIVATE_MOCK_PROVIDER_DIAGNOSTIC" not in await page.locator("#agent-result").inner_text()
                assert await page.locator("#agent-run").is_disabled()
                assert not await page.locator("#agent-consent").is_checked()
                assert len(invocations) == 1
                assert requests.count(("POST", "/api/agent/review")) == 2

                # Provider auth, balance and throttling are DIFFERENT actionable
                # conditions. Both the request and its failure are mocked.
                # No provider body, secret, unsupported command or new paid
                # request may ever be exposed or automatically retried.
                for error_code, visible in (
                    ("provider_authentication_failed", "인증 거부(401)"),
                    ("provider_insufficient_balance", "잔액 부족(402)"),
                    ("provider_rate_limited", "요청 제한(429)"),
                    ("provider_timeout", "시간 초과"),
                    ("provider_transport_or_response_invalid", "응답 형식 검증"),
                ):
                    def fail_with_allowlisted_code(_context, _key, code=error_code):
                        raise agent._ProviderError(code)
                    agent._invoke_deepseek = fail_with_allowlisted_code
                    before_count = requests.count(("POST", "/api/agent/review"))
                    await page.locator("#agent-preview").click()
                    await page.locator("#agent-preview-content:not([hidden])").wait_for()
                    await page.locator("#agent-consent").check()
                    await page.locator("#agent-run").click()
                    await page.wait_for_function(
                        "(text) => document.querySelector('#agent-result').textContent.includes(text)",
                        arg=visible)
                    result_text = await page.locator("#agent-result").inner_text()
                    assert "자동 재요청하지 않습니다" in result_text
                    assert "PRIVATE_MOCK_PROVIDER_DIAGNOSTIC" not in result_text
                    assert "SYNTHETIC_STAGE6_NO_NETWORK_KEY" not in result_text
                    assert "전송 여부 확인 불가" in await page.locator("#agent-feedback").inner_text()
                    assert requests.count(("POST", "/api/agent/review")) == before_count + 1
                    assert await page.locator("#agent-run").is_disabled()

                agent._invoke_deepseek = fake_invoke

                # A response can reach the server/paid provider BEFORE the
                # operator edits the form and aborts only their browser wait.
                # Never erase that uncertainty or display a stale AI result.
                delayed_started = asyncio.Event()
                delayed_attempts = []
                async def delayed_ai_reply(route):
                    req = route.request
                    delayed_attempts.append(req.post_data_buffer)
                    response = client.post(
                        "/api/agent/review", content=req.post_data_buffer or b"",
                        headers={"content-type": "application/json"})
                    assert response.status_code == 200
                    assert response.json()["status"] == "reviewed"
                    delayed_started.set()
                    await asyncio.sleep(.5)
                    try:
                        await route.fulfill(status=response.status_code,
                            body=response.content,
                            headers={"content-type": "application/json"})
                    except Exception:
                        # The browser may cancel its pending fetch when the
                        # user changes input. That cannot refund a sent request.
                        pass
                await page.route(BASE + "/api/agent/review", delayed_ai_reply)
                await page.locator("#agent-preview").click()
                await page.locator("#agent-preview-content:not([hidden])").wait_for()
                await page.locator("#agent-consent").check()
                await page.locator("#agent-run").click()
                await asyncio.wait_for(delayed_started.wait(), timeout=7)
                assert len(delayed_attempts) == 1
                assert len(invocations) == 2
                await page.locator("#triage-symptom").fill("STAGE6_USER_CHANGED_DURING_PAID_CALL")
                assert "비용이 발생했을 수 있어요" in await page.locator("#agent-feedback").inner_text()
                assert await page.locator("#agent-run").is_disabled()
                assert not await page.locator("#agent-consent").is_checked()
                await page.wait_for_timeout(650)
                assert "AI 참고 검토 순서" not in await page.locator("#agent-result").inner_text()
                assert len(delayed_attempts) == 1
                await page.unroute(BASE + "/api/agent/review", delayed_ai_reply)

                await page.locator("#ml-upload").set_input_files({
                    "name": "source.csv", "mimeType": "text/csv",
                    "buffer": (b"asset_id,trial_id,source_id,vibration_rms_m_s2,vibration_peak_m_s2,current_rms_a\n"
                               b"K001,T1,paderborn-bearing-datacenter,1.0,2.0,0.5\n")})
                await page.locator("#ml-run").click()
                await page.wait_for_function(
                    "document.querySelector('#ml-feedback').textContent.includes('검증된')")
                assert "모델이 없으므로" in await page.locator("#ml-feedback").inner_text()

                await page.locator("#triage-hazard").select_option("yes")
                assert await page.locator("#agent-run").is_disabled()
                assert await page.locator("#agent-preview").is_disabled()
                assert await page.locator("#ml-run").is_disabled()
                assert len(invocations) == 2
                assert not errors, errors
                await browser.close()
    finally:
        agent._invoke_deepseek = saved_fn
        if saved_key is None:
            os.environ.pop("DEEPSEEK_API_KEY", None)
        else:
            os.environ["DEEPSEEK_API_KEY"] = saved_key
    print("STAGE6_BROWSER_INTEGRATION_PASS 1 mocked AI call, preview token, ML hold, hazard hold, JS errors:", len(errors))


if __name__ == "__main__":
    asyncio.run(run())
