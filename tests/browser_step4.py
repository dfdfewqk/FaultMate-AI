"""P7.2 Step 4: optional knowledge requests cannot block diagnosis.

Playwright routes local HTML/fetch through FastAPI TestClient due to browser localhost policy.
Covers slow status, slow/failing knowledge sources, no prefetch, retry, and navigation.
"""
import asyncio
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from playwright.async_api import async_playwright
from faultmate.app import app

BASE = 'https://faultmate.test'

async def run():
    root=Path(__file__).resolve().parents[1]
    client=TestClient(app)
    hits=[]
    js_errors=[]
    source_failure=True
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        page=await browser.new_page(viewport={'width':1120,'height':830})
        page.on('pageerror',lambda e:js_errors.append(str(e)))
        async def router(route):
            nonlocal source_failure
            req=route.request
            path=urlsplit(req.url).path
            hits.append(path)
            if path == '/api/status':
                await asyncio.sleep(1.35)
            if path == '/api/integration/capabilities':
                await asyncio.sleep(1.35)
            if path.startswith('/api/knowledge/'):
                await asyncio.sleep(.45)
            if path == '/api/knowledge/sources' and source_failure:
                source_failure=False
                await route.fulfill(status=503,body='unavailable',headers={'content-type':'text/plain'})
                return
            response=(client.post(path,content=req.post_data_buffer or b'',headers={'content-type':req.headers.get('content-type','application/json')})
                if req.method=='POST' else client.get(path+('?' + urlsplit(req.url).query if urlsplit(req.url).query else '')))
            await route.fulfill(status=response.status_code,body=response.content,headers={'content-type':response.headers.get('content-type','text/plain')})
        await page.route(BASE+'/**',router)
        html=(root/'web/index.html').read_text(encoding='utf-8')
        html=html.replace('<link rel="stylesheet" href="/assets/style.css"/>','').replace('<script src="/assets/app.js" defer></script>','').replace('<head>','<head><base href="https://faultmate.test/">')
        await page.set_content(html)
        await page.add_style_tag(content=(root/'web/style.css').read_text(encoding='utf-8'))
        await page.add_script_tag(content=(root/'web/app.js').read_text(encoding='utf-8'))
        await page.wait_for_function("document.querySelector('#triage-feedback').textContent.includes('설비와 사례')",timeout=1100)
        assert '/api/knowledge/sources' not in hits
        assert '/api/knowledge/cases' not in hits
        assert '/api/knowledge/cases/CONV-001' not in hits
        assert await page.locator('#status').inner_text() == '서버 연결 확인 중'
        assert await page.locator('#agent-status').text_content() == '상태 확인 중'
        await page.locator('#triage-equipment').select_option('컨베이어')
        await page.locator('#triage-case').select_option('CONV-001')
        await page.locator('#triage-submit').click()
        await page.locator('#triage-result .result-cause').first.wait_for(timeout=1100)
        assert '/api/knowledge/sources' not in hits
        # Open the previously collapsed knowledge room. First source call fails;
        # case browsing must remain available, core triage must still work.
        await page.locator('#knowledge-panel summary').click()
        await page.locator('button.knowledge-item').first.wait_for(timeout=4000)
        assert await page.locator('button.knowledge-item').count() == 7
        await page.wait_for_function("document.querySelector('#knowledge-detail').textContent.includes('출처 링크 조회에 실패')", timeout=4000)
        assert '/api/knowledge/sources' in hits
        assert hits.count('/api/knowledge/sources') == 1
        await page.locator('#knowledge-panel summary').click()
        await page.locator('#knowledge-panel summary').click()
        await page.wait_for_function("document.querySelector('#knowledge-detail').textContent.includes('원인 후보')",timeout=4000)
        await page.wait_for_timeout(150)
        assert hits.count('/api/knowledge/sources') == 2, hits
        await page.locator('#equipment-filter').select_option('모터')
        await page.wait_for_function("document.querySelectorAll('button.knowledge-item').length === 2",timeout=3500)
        assert await page.locator('button.knowledge-item').count() == 2
        await page.wait_for_function("document.querySelector('#knowledge-detail').textContent.includes('원인 후보')",timeout=4000)
        await page.locator('#knowledge-panel summary').click()
        before=len([p for p in hits if p.startswith('/api/knowledge/')])
        await page.locator('#knowledge-panel summary').click()
        await page.wait_for_timeout(550)
        after=len([p for p in hits if p.startswith('/api/knowledge/')])
        assert before == after,(before,after)
        assert not js_errors,js_errors
        await browser.close()
    print('P72_STEP4_BROWSER_PASS',17,'checks; js_errors',len(js_errors))

if __name__=='__main__':
    asyncio.run(run())
