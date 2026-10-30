"""P7.2 step 5 clipboard and invalidation browser checks.

Chromium UI with in-process FastAPI requests; not direct Windows E2E.
"""
import asyncio
from pathlib import Path
from urllib.parse import urlsplit
from fastapi.testclient import TestClient
from playwright.async_api import async_playwright
from faultmate.app import app
BASE = 'https://faultmate.test'


async def run():
    root = Path(__file__).resolve().parents[1]
    client = TestClient(app)
    requests, errors = [], []
    count = 0
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(executable_path='/usr/bin/chromium',
            headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        page = await browser.new_page(viewport={'width':1280,'height':800})
        page.on('pageerror',lambda error: errors.append(str(error)))
        async def router(route):
            req = route.request
            path = urlsplit(req.url).path
            requests.append((req.method,path))
            result = (client.post(path,content=req.post_data_buffer or b'',
                      headers={'content-type':req.headers.get('content-type','application/json')})
                      if req.method=='POST' else client.get(path +
                      ('?' + urlsplit(req.url).query if urlsplit(req.url).query else '')))
            await route.fulfill(status=result.status_code,body=result.content,
               headers={'content-type':result.headers.get('content-type','text/plain')})
        await page.route(BASE+'/**',router)
        html = (root/'web/index.html').read_text(encoding='utf-8')
        html = html.replace('<link rel="stylesheet" href="/assets/style.css"/>','')
        html = html.replace('<script src="/assets/app.js" defer></script>','')
        html = html.replace('<head>','<head><base href="https://faultmate.test/">')
        await page.set_content(html)
        await page.add_style_tag(content=(root/'web/style.css').read_text(encoding='utf-8'))
        await page.add_script_tag(content=(root/'web/app.js').read_text(encoding='utf-8'))
        await page.wait_for_function("document.querySelector('#triage-feedback').textContent.includes('설비와 사례')")
        btn = page.locator('#triage-result .result-copy-button')
        assert await btn.count()==0; count+=1
        assert await page.locator('#integration-panel').evaluate('(el)=>!el.open');count+=1
        assert await page.locator('#agent-status').count()==1;count+=1
        await page.evaluate("""() => {window.__copied=[]; Object.defineProperty(navigator,'clipboard',
          {configurable:true,value:{writeText:async s=>{window.__copied.push(s)}}});}""")
        await page.locator('#triage-equipment').select_option('컨베이어')
        await page.locator('#triage-symptom').fill('벨트 이송이 멈춤')
        await page.locator('#triage-case').select_option('CONV-001')
        await page.locator('#triage-submit').click()
        await btn.wait_for();count+=1
        assert await btn.is_enabled();count+=1
        before=len(requests)
        await btn.click()
        await page.wait_for_function('window.__copied.length === 1')
        assert len(requests)==before;count+=1
        copied=await page.evaluate('window.__copied[0]')
        for word in ('FaultMate AI','로컬 고장 검토 요약','벨트 이송이 멈춤',
             '실제 원인 미확정','정비 작업 허가 아님','원인 후보',
             '안전 조건:','중단·보고 기준:','AI·ML 분석 결과는 포함하지 않습니다'):
            assert word in copied,word
            count+=1
        assert '가상 시험 입력' not in copied;count+=1
        await page.locator('#triage-result').screenshot(path='/mnt/data/FaultMate_AI_P72_Step5_Preview.png')
        await page.wait_for_function("document.querySelector('.result-copy-feedback').textContent.includes('요약을 복사했습니다')")
        count+=1
        await page.locator('#triage-hazard').select_option('yes')
        assert await btn.count()==0;count+=1
        assert '긴급 위험' in await page.locator('#triage-result').inner_text();count+=1
        await page.locator('#triage-hazard').select_option('unknown')
        await page.locator('#triage-submit').click()
        await btn.wait_for()
        await page.locator('#triage-symptom').fill('다른 증상')
        assert await btn.count()==0;count+=1
        await page.locator('#triage-demo').click()
        await page.locator('#triage-submit').click()
        await btn.wait_for()
        await btn.click()
        await page.wait_for_function('window.__copied.length === 2')
        assert '가상 시험 입력' in await page.evaluate('window.__copied[1]');count+=1
        await page.locator('#triage-reset').click()
        assert await btn.count()==0;count+=1
        await page.locator('#triage-equipment').select_option('모터')
        await page.locator('#triage-case').select_option('MOTOR-001')
        await page.locator('#triage-submit').click()
        await btn.wait_for()
        await page.evaluate("""() => {Object.defineProperty(navigator,'clipboard',
           {configurable:true,value:{writeText:async ()=>{throw Error('denied')}}});}""")
        await btn.click()
        await page.wait_for_function("document.querySelector('.result-copy-feedback').textContent.includes('자동 복사에 실패')")
        count+=1
        assert await btn.is_enabled();count+=1
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth+1');count+=1
        assert not errors,errors
        count+=1
        await browser.close()
    print('P72_STEP5_BROWSER_PASS',count,'checks; js_errors',len(errors))

if __name__=='__main__':
    asyncio.run(run())
