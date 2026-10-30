"""P7.2 final: recover failed optional detail fetch without blocking diagnosis.

Browser uses in-process FastAPI responses because direct localhost navigation is
unavailable in the test container; it is not a Windows end-to-end test.
"""
import asyncio
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from playwright.async_api import async_playwright
from faultmate.app import app

BASE = "https://faultmate.test"


async def run():
    root = Path(__file__).resolve().parents[1]
    client = TestClient(app)
    requests = []
    errors = []
    failure_left = True
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path="/usr/bin/chromium", headless=True,
                                           args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("pageerror", lambda err: errors.append(str(err)))

        async def route_request(route):
            nonlocal failure_left
            req = route.request
            path = urlsplit(req.url).path
            requests.append(path)
            if path == "/api/knowledge/cases/CONV-001" and failure_left:
                failure_left = False
                await route.fulfill(status=503, body="temporarily unavailable")
                return
            res = (client.post(path, content=req.post_data_buffer or b"",
                               headers={"content-type": req.headers.get("content-type", "application/json")})
                   if req.method == "POST" else client.get(path + (
                       "?" + urlsplit(req.url).query if urlsplit(req.url).query else "")))
            await route.fulfill(status=res.status_code, body=res.content,
                                headers={"content-type": res.headers.get("content-type", "text/plain")})

        await page.route(BASE + "/**", route_request)
        html = (root / "web/index.html").read_text(encoding="utf-8")
        html = html.replace('<link rel="stylesheet" href="/assets/style.css"/>', "")
        html = html.replace('<script src="/assets/app.js" defer></script>', "")
        html = html.replace("<head>", '<head><base href="https://faultmate.test/">')
        await page.set_content(html)
        await page.add_style_tag(content=(root / "web/style.css").read_text(encoding="utf-8"))
        await page.add_script_tag(content=(root / "web/app.js").read_text(encoding="utf-8"))
        await page.wait_for_function("document.querySelector('#triage-feedback').textContent.includes('설비와 사례')")
        assert not any(x.startswith("/api/knowledge/") for x in requests)
        await page.locator("#triage-equipment").select_option("모터")
        await page.locator("#triage-case").select_option("MOTOR-001")
        await page.locator("#triage-submit").click()
        await page.locator("#triage-result .result-cause").first.wait_for()
        assert not any(x.startswith("/api/knowledge/") for x in requests)
        await page.locator("#knowledge-panel summary").click()
        await page.wait_for_function("document.querySelector('#knowledge-detail').textContent.includes('재시도합니다')")
        assert requests.count("/api/knowledge/cases/CONV-001") == 1
        await page.locator("#knowledge-panel summary").click()
        await page.locator("#knowledge-panel summary").click()
        await page.wait_for_function("document.querySelector('#knowledge-detail').textContent.includes('원인 후보')")
        assert requests.count("/api/knowledge/cases/CONV-001") == 2
        await page.locator("#knowledge-panel summary").click()
        await page.locator("#knowledge-panel summary").click()
        await page.wait_for_timeout(200)
        assert requests.count("/api/knowledge/cases/CONV-001") == 2, requests
        assert not errors, errors
        await browser.close()
    print("P72_FINAL_BROWSER_PASS 7 checks; js_errors", len(errors))

if __name__ == "__main__":
    asyncio.run(run())
