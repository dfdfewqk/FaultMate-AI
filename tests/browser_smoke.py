"""P5 browser smoke test with real FastAPI responses routed in-process.

Optional QA-only dependencies: playwright + Chromium. No external network required.
The Chromium sandbox in this execution environment blocks loopback navigation;
this routes each HTTP request through FastAPI TestClient instead.
"""
import asyncio
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from playwright.async_api import async_playwright
from faultmate.app import app

BASE = "https://faultmate.test"


async def run():
    errors = []
    counts = {"server_routes": 0, "ui_checks": 0}
    client = TestClient(app)
    async with async_playwright() as play:
        browser = await play.chromium.launch(
            executable_path="/usr/bin/chromium", headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        delayed = False
        delayed_ml = False

        async def http_route(route):
            nonlocal delayed, delayed_ml
            req = route.request
            path = urlsplit(req.url).path
            if path.startswith("/api/diagnostics/evaluate") and delayed:
                await asyncio.sleep(.6)
            if path == "/api/ml/inspect" and delayed_ml:
                await asyncio.sleep(.65)
            if req.method == "POST":
                response = client.post(path, content=req.post_data_buffer or b"", headers={"content-type": req.headers.get("content-type", "application/json")})
            else:
                response = client.get(path + ("?" + urlsplit(req.url).query if urlsplit(req.url).query else ""))
            counts["server_routes"] += 1
            await route.fulfill(status=response.status_code, body=response.content,
                                headers={"Content-Type": response.headers.get("content-type", "text/plain")})

        await page.route(BASE + "/**", http_route)
        root = Path(__file__).resolve().parents[1]
        html = (root / "web/index.html").read_text(encoding="utf-8")
        html = html.replace('<link rel="stylesheet" href="/assets/style.css"/>', '')
        html = html.replace('<script src="/assets/app.js" defer></script>', '')
        html = html.replace('<head>', '<head><base href="https://faultmate.test/">')
        await page.set_content(html)
        await page.add_style_tag(content=(root / "web/style.css").read_text(encoding="utf-8"))
        await page.add_script_tag(content=(root / "web/app.js").read_text(encoding="utf-8"))
        await page.wait_for_timeout(700)
        assert await page.locator("#status").inner_text() == "로컬 서버 연결 정상"
        assert await page.locator("#agent-status").text_content() == "미연결"
        assert "미연결" in await page.locator("#integration-ml").text_content()
        assert await page.locator("button.knowledge-item").count() == 0
        counts["ui_checks"] += 4
        assert await page.locator('#integration-panel').evaluate('(el) => !el.open')
        assert await page.locator('#knowledge-panel').evaluate('(el) => !el.open')
        assert await page.locator('#triage-more').evaluate('(el) => !el.open')
        counts["ui_checks"] += 3
        await page.screenshot(path='/mnt/data/FaultMate_AI_Simple_Initial.png',full_page=True)

        await page.locator("#triage-equipment").select_option("컨베이어")
        await page.locator("#triage-case").select_option("CONV-001")
        await page.locator('select[data-key="visible_jam"]').select_option("yes")
        await page.locator("#triage-submit").click()
        await page.locator("#triage-result .result-cause").first.wait_for(timeout=7000)
        result = await page.locator("#triage-result").inner_text()
        assert "고장 원인을 확정하지 않았습니다" in result
        assert "추가 확인 우선" in result
        counts["ui_checks"] += 2

        await page.locator("#triage-hazard").select_option("yes")
        assert await page.locator("#triage-submit").is_disabled()
        assert "긴급 위험 징후" in await page.locator("#triage-result").inner_text()
        await page.locator("#triage-hazard").select_option("no")
        assert await page.locator("#triage-submit").is_enabled()
        assert "추가 확인 우선" not in await page.locator("#triage-result").inner_text()
        counts["ui_checks"] += 4

        # In-flight request MUST NOT overwrite an emergency hold.
        delayed = True
        await page.locator("#triage-submit").click()
        assert await page.locator("#triage-submit").is_disabled()
        await page.locator("#triage-hazard").select_option("yes")
        await page.wait_for_timeout(850)
        assert await page.locator("#triage-submit").is_disabled()
        assert "긴급 위험 징후" in await page.locator("#triage-result").inner_text()
        assert "원인 미확정" not in await page.locator("#triage-result").inner_text()
        counts["ui_checks"] += 4
        delayed = False

        await page.locator("#triage-reset").click()
        assert await page.locator("#triage-submit").is_disabled()
        assert await page.locator("#triage-equipment").input_value() == ""
        assert "입력이 초기화" in await page.locator("#triage-result").inner_text()
        counts["ui_checks"] += 3

        await page.locator("#knowledge-panel summary").click()
        await page.wait_for_function("document.querySelectorAll('button.knowledge-item').length === 7", timeout=5000)
        await page.locator("#equipment-filter").select_option("모터")
        await page.wait_for_function("document.querySelectorAll('button.knowledge-item').length === 2", timeout=5000)
        assert await page.locator("button.knowledge-item").count() == 2
        await page.locator('button.knowledge-item').last.click()
        assert await page.locator('button.knowledge-item[aria-pressed="true"]').count() == 1
        counts["ui_checks"] += 2

        # New P6 browser controls: consent-gated context review and fail-closed ML.
        await page.locator("#triage-equipment").select_option("컨베이어")
        await page.locator("#triage-case").select_option("CONV-001")
        await page.locator("#integration-panel summary").click()
        await page.locator("#agent-preview").click()
        await page.locator("#agent-preview-content:not([hidden])").wait_for(timeout=5000)
        preview_text = await page.locator("#agent-preview-content").inner_text()
        assert 'CONV-001' in preview_text and 'candidate_causes' in preview_text
        assert await page.locator("#agent-run").is_disabled()
        counts["ui_checks"] += 3
        await page.locator("#agent-consent").check()
        assert await page.locator("#agent-run").is_enabled()
        # Reopening preview invalidates earlier approval instead of reusing it.
        await page.locator("#agent-preview").click()
        assert not await page.locator("#agent-consent").is_checked()
        assert await page.locator("#agent-run").is_disabled()
        await page.locator("#agent-preview-content:not([hidden])").wait_for(timeout=5000)
        await page.locator("#agent-consent").check()
        await page.locator("#agent-run").click()
        counts["ui_checks"] += 2
        await page.wait_for_function("document.querySelector('#agent-feedback').textContent.includes('로컬 진단 사용')")
        assert 'API 키' in await page.locator("#agent-result").inner_text()
        counts["ui_checks"] += 3
        await page.locator("#triage-hazard").select_option("yes")
        assert await page.locator("#agent-run").is_disabled()
        assert await page.locator("#agent-preview-content").is_hidden()
        assert await page.locator("#ml-run").is_disabled()
        counts["ui_checks"] += 3
        await page.locator("#triage-hazard").select_option("no")
        assert await page.locator("#ml-run").is_enabled()
        counts["ui_checks"] += 1
        await page.locator("#ml-upload").set_input_files({"name":"features.csv","mimeType":"text/csv",
           "buffer":b"asset_id,trial_id,source_id,vibration_rms_m_s2,vibration_peak_m_s2,current_rms_a\nbear1,run1,dataset,1.0,2.0,1.0\n"})
        await page.locator("#ml-run").click()
        await page.wait_for_function("document.querySelector('#ml-feedback').textContent.includes('검증된')")
        assert '검증된 베어링 ML 모델이 없으므로' in await page.locator("#ml-feedback").inner_text()
        counts["ui_checks"] += 2
        # A file changed while a local analysis was in-flight must not display
        # results corresponding to the previously selected file.
        delayed_ml = True
        await page.locator("#ml-run").click()
        await page.locator("#ml-upload").set_input_files({"name":"changed.csv","mimeType":"text/csv",
           "buffer":b"asset_id,trial_id,source_id,vibration_rms_m_s2,vibration_peak_m_s2,current_rms_a\nbear2,run2,dataset,2.0,4.0,1.0\n"})
        await page.wait_for_timeout(800)
        assert "파일이 변경" in await page.locator("#ml-feedback").inner_text()
        assert await page.locator("#ml-result").inner_text() == ""
        counts["ui_checks"] += 2
        delayed_ml = False
        # Malformed fragments must not interrupt later UI interactions.
        await page.evaluate("location.hash = '%E0%A4%A'; window.dispatchEvent(new HashChangeEvent('hashchange'))")
        assert await page.locator("#ml-run").is_enabled()
        counts["ui_checks"] += 1
        assert errors == [], errors
        counts["ui_checks"] += 1
        await page.screenshot(path="/mnt/data/FaultMate_AI_Simple_Test_Screenshot.png", full_page=True)
        await browser.close()
    print("PASS", counts, "console_errors", len(errors))


if __name__ == "__main__":
    asyncio.run(run())
