"""P7.2-2 safety state transitions in Chromium, using actual FastAPI responses."""
import asyncio
from pathlib import Path
from urllib.parse import urlsplit
from fastapi.testclient import TestClient
from playwright.async_api import async_playwright
from faultmate.app import app

BASE='https://faultmate.test'
async def run():
    count=0
    errors=[]
    network=[]
    client=TestClient(app)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        page=await browser.new_page(viewport={'width':1280,'height':850})
        page.on('pageerror',lambda error: errors.append(str(error)))
        async def route_handler(route):
            req=route.request
            path=urlsplit(req.url).path
            network.append(path)
            response=(client.post(path,content=req.post_data_buffer or b'',headers={'content-type':req.headers.get('content-type','application/json')})
                      if req.method=='POST' else client.get(path + (('?' + urlsplit(req.url).query) if urlsplit(req.url).query else '')))
            await route.fulfill(status=response.status_code,body=response.content,headers={'Content-Type':response.headers.get('content-type','text/plain')})
        await page.route(BASE+'/**',route_handler)
        root=Path(__file__).resolve().parents[1]
        html=(root/'web/index.html').read_text(encoding='utf-8')
        html=html.replace('<link rel="stylesheet" href="/assets/style.css"/>','').replace('<script src="/assets/app.js" defer></script>','').replace('<head>','<head><base href="https://faultmate.test/">')
        await page.set_content(html)
        await page.add_style_tag(content=(root/'web/style.css').read_text(encoding='utf-8'))
        await page.add_script_tag(content=(root/'web/app.js').read_text(encoding='utf-8'))
        await page.wait_for_function("document.querySelector('#triage-feedback').textContent.includes('설비와 사례')")
        status=page.locator('#hazard-status')
        assert await status.is_visible()
        assert '안전 상태 미확인' in await status.inner_text()
        assert 'is-unknown' in (await status.get_attribute('class'))
        count+=3
        # A new operator sees hazard status before diagnosis and can review read-only info under unknown.
        assert await page.locator('#hazard-gate').bounding_box() is not None
        y1=(await page.locator('#hazard-gate').bounding_box())['y']
        y2=(await page.locator('#triage-suggestions').bounding_box())['y']
        assert y1 < y2
        count+=1
        await page.locator('#triage-equipment').select_option('컨베이어')
        await page.locator('#triage-case').select_option('CONV-001')
        await page.locator('#triage-submit').click()
        await page.locator('#triage-result .result-cause').first.wait_for()
        assert '긴급 위험 확인 전' in await page.locator('#triage-result').inner_text()
        count+=1
        await page.locator('#triage-hazard').select_option('no')
        assert '안전하다는 인증' in await status.inner_text()
        assert 'is-no' in (await status.get_attribute('class'))
        assert '정비 작업 허가' in await status.inner_text()
        assert await page.locator('#triage-submit').is_enabled()
        count+=4
        await page.locator('#triage-submit').click()
        await page.locator('#triage-result .result-cause').first.wait_for()
        assert '안전 인증·정비 작업 허가 아님' in await page.locator('#triage-result').inner_text()
        count+=1
        # A hazard report blocks triage, suggestions, AI preview/run, ML file/run.
        await page.locator('#triage-hazard').select_option('yes')
        assert '긴급 위험 징후 있음' in await status.inner_text()
        assert 'is-yes' in (await status.get_attribute('class'))
        assert await page.locator('#triage-submit').is_disabled()
        assert await page.locator('#triage-demo').is_disabled()
        assert await page.locator('#agent-preview').is_disabled()
        assert await page.locator('#agent-run').is_disabled()
        assert await page.locator('#ml-upload').is_disabled()
        assert await page.locator('#ml-run').is_disabled()
        assert '긴급 위험 징후' in await page.locator('#triage-result').inner_text()
        assert await page.locator('#triage-result .result-cause').count() == 0
        count+=10
        await page.locator('#triage-hazard').select_option('unknown')
        assert '안전 상태 미확인' in await status.inner_text()
        assert await page.locator('#triage-submit').is_enabled()
        assert await page.locator('#ml-run').is_enabled()
        count+=3
        await page.locator('#triage-reset').click()
        assert await page.locator('#triage-hazard').input_value() == 'unknown'
        assert '안전 상태 미확인' in await status.inner_text()
        count+=2
        await page.set_viewport_size({'width':390,'height':844})
        await page.wait_for_timeout(120)
        assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
        count+=1
        await page.screenshot(path='/mnt/data/FaultMate_AI_P72_Step2_Preview.png',full_page=True)
        assert not [x for x in network if '/api/agent/' in x or '/api/ml/' in x]
        assert not errors,errors
        count+=2
        await browser.close()
    print('P72_STEP2_BROWSER_PASS',count,'checks; js_errors',len(errors))

if __name__=='__main__':
    asyncio.run(run())
