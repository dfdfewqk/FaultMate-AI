"""P7.2-1 actual Chromium UI with local FastAPI HTTP responses routed in-process."""
import asyncio
from pathlib import Path
from urllib.parse import urlsplit
from fastapi.testclient import TestClient
from playwright.async_api import async_playwright
from faultmate.app import app

BASE='https://faultmate.test'
async def run():
    checks=0
    errors=[]
    requests=[]
    client=TestClient(app)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        page=await browser.new_page(viewport={'width':1280,'height':850})
        page.on('pageerror',lambda error: errors.append(str(error)))
        async def route_handler(route):
            req=route.request
            path=urlsplit(req.url).path
            requests.append(path)
            if req.method=='POST':
                response=client.post(path,content=req.post_data_buffer or b'',headers={'content-type':req.headers.get('content-type','application/json')})
            else:
                response=client.get(path+(('?'+urlsplit(req.url).query) if urlsplit(req.url).query else ''))
            await route.fulfill(status=response.status_code,body=response.content,headers={'Content-Type':response.headers.get('content-type','text/plain')})
        await page.route(BASE+'/**',route_handler)
        root=Path(__file__).resolve().parents[1]
        html=(root/'web/index.html').read_text(encoding='utf8')
        html=html.replace('<link rel="stylesheet" href="/assets/style.css"/>','').replace('<script src="/assets/app.js" defer></script>','').replace('<head>','<head><base href="https://faultmate.test/">')
        await page.set_content(html)
        await page.add_style_tag(content=(root/'web/style.css').read_text(encoding='utf8'))
        await page.add_script_tag(content=(root/'web/app.js').read_text(encoding='utf8'))
        await page.wait_for_function("document.querySelector('#triage-feedback').textContent.includes('설비와 사례')")
        assert await page.locator('#triage-symptom').is_visible()
        assert not await page.locator('#triage-submit').is_enabled()
        checks+=2
        await page.locator('#triage-equipment').select_option('컨베이어')
        await page.locator('#triage-symptom').fill('모터 소리가 나지만 벨트가 움직이지 않음')
        await page.locator('button[data-suggest-case="CONV-001"]').wait_for(timeout=5000)
        assert await page.locator('#triage-case').input_value() == ''
        assert await page.locator('#triage-submit').is_disabled()
        checks+=2
        await page.screenshot(path='/mnt/data/FaultMate_AI_P72_Step1_Preview.png',full_page=True)
        await page.locator('button[data-suggest-case="CONV-001"]').click()
        assert await page.locator('#triage-case').input_value() == 'CONV-001'
        assert await page.locator('#triage-submit').is_enabled()
        assert await page.locator('select[data-key="motor_rotates_log"]').count() == 1
        checks+=3
        await page.locator('#triage-submit').click()
        await page.locator('#triage-result .result-cause').first.wait_for(timeout=5000)
        assert '고장 원인을 확정하지 않았습니다' in await page.locator('#triage-result').inner_text()
        checks+=1
        # Editing symptoms invalidates previous selection/observations/result.
        await page.locator('#triage-symptom').fill('미등록 이상 증상')
        assert await page.locator('#triage-case').input_value() == ''
        assert await page.locator('#triage-submit').is_disabled()
        assert await page.locator('#triage-result .result-cause').count() == 0
        await page.wait_for_function("document.querySelector('#triage-suggestion-list').textContent.includes('일치하는 등록 사례가 없습니다')")
        assert await page.locator('#triage-suggestion-list button').count() == 0
        checks+=4
        # Still permit manual choice if the operator knows an actual registered case.
        await page.locator('#triage-case').select_option('CONV-002')
        assert await page.locator('#triage-submit').is_enabled()
        checks+=1
        # Emergency cancels recommendations and blocks diagnosis even when the UI has a case.
        await page.locator('#triage-symptom').fill('모터 소리만 나고 벨트가 움직이지 않음')
        await page.locator('#triage-hazard').select_option('yes')
        await page.wait_for_timeout(450)
        assert await page.locator('#triage-submit').is_disabled()
        assert await page.locator('#triage-suggestion-list button').count() == 0
        assert '긴급 위험 징후' in await page.locator('#triage-result').inner_text()
        checks+=3
        await page.locator('#triage-reset').click()
        assert await page.locator('#triage-equipment').input_value() == ''
        assert await page.locator('#triage-symptom').input_value() == ''
        assert await page.locator('#triage-suggestion-list button').count() == 0
        checks+=3
        # Mobile layout should not scroll horizontally.
        await page.set_viewport_size({'width':390,'height':844})
        await page.wait_for_timeout(100)
        assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
        checks+=1
        assert not [path for path in requests if '/api/agent/' in path or '/api/ml/' in path]
        assert errors == [],errors
        checks+=2
        await browser.close()
    print('P72_STEP1_BROWSER_PASS',checks,'checks','js_errors',len(errors))
if __name__=='__main__':
    asyncio.run(run())
