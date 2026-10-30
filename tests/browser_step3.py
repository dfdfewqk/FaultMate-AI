"""P7.2 step 3 operator result layout: read-only, no lost evidence.
Uses browser + genuine FastAPI JSON routed via TestClient because local navigation is blocked.
"""
import asyncio
from pathlib import Path
from urllib.parse import urlsplit
from fastapi.testclient import TestClient
from playwright.async_api import async_playwright
from faultmate.app import app

BASE='https://faultmate.test'

async def run():
    root=Path(__file__).resolve().parents[1]
    client=TestClient(app)
    count=0; js_errors=[]
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        page=await browser.new_page(viewport={'width':1280,'height':900})
        page.on('pageerror',lambda e: js_errors.append(str(e)))
        async def router(route):
            req=route.request
            path=urlsplit(req.url).path
            resp=(client.post(path,content=req.post_data_buffer or b'',headers={'content-type':req.headers.get('content-type','application/json')})
                  if req.method=='POST' else client.get(path+'?'+urlsplit(req.url).query if urlsplit(req.url).query else path))
            await route.fulfill(status=resp.status_code,body=resp.content,headers={'content-type':resp.headers.get('content-type','text/plain')})
        await page.route(BASE+'/**',router)
        html=(root/'web/index.html').read_text(encoding='utf-8')
        html=html.replace('<link rel="stylesheet" href="/assets/style.css"/>','').replace('<script src="/assets/app.js" defer></script>','').replace('<head>','<head><base href="https://faultmate.test/">')
        await page.set_content(html)
        await page.add_style_tag(content=(root/'web/style.css').read_text(encoding='utf-8'))
        await page.add_script_tag(content=(root/'web/app.js').read_text(encoding='utf-8'))
        await page.wait_for_function("document.querySelector('#triage-feedback').textContent.includes('설비와 사례')")
        await page.locator('#triage-equipment').select_option('컨베이어')
        await page.locator('#triage-case').select_option('CONV-001')
        await page.locator('[data-key="visible_jam"]').select_option('yes')
        await page.locator('#triage-submit').click()
        await page.locator('#triage-result .result-cause').first.wait_for()
        data=client.post('/api/diagnostics/evaluate',json={'equipment':'컨베이어','case_id':'CONV-001','observations':{'visible_jam':'yes'},'emergency_hazard':'unknown'}).json()
        result=page.locator('#triage-result')
        details=page.locator('#triage-result-details')
        assert await details.count()==1; count+=1
        assert not await details.evaluate('(el) => el.open'); count+=1
        assert await result.locator('.result-cause').count()==len(data['candidate_causes']); count+=1
        for c in data['candidate_causes']:
            assert c['candidate'] in await result.inner_text();count+=1
        for text in (data['safety_gate'],data['stop_escalation'],'긴급 위험 확인 전','고장 원인을 확정하지 않았습니다'):
            assert text in await result.inner_text();count+=1
        assert data['sources'][0]['title'] not in await result.inner_text();count+=1
        assert await details.locator('summary').is_visible();count+=1
        await details.locator('summary').click()
        assert await details.evaluate('(el) => el.open');count+=1
        for source in data['sources']:
            assert source['title'] in await details.inner_text(); count+=1
            assert source['limit'] in await details.inner_text(); count+=1
        questions=[q['question'] for q in data['next_questions']]+data['additional_information_questions']
        for question in questions:
            assert question in await details.inner_text(); count+=1
        assert data['notice'] in await details.inner_text(); count+=1
        assert data['selection_basis'] in await details.inner_text(); count+=1
        # A new result is collapsed again, so irrelevant previous expansion isn't preserved.
        await page.locator('#triage-submit').click()
        await page.locator('#triage-result .result-cause').first.wait_for()
        assert not await page.locator('#triage-result-details').evaluate('(el) => el.open');count+=1
        # Emergency status cannot leave the previous diagnosis or disclosure visible.
        await page.locator('#triage-hazard').select_option('yes')
        assert '긴급 위험' in await result.inner_text();count+=1
        assert await page.locator('#triage-result-details').count()==0;count+=1
        assert await result.locator('.result-cause').count()==0;count+=1
        # Responsive layout after completing a diagnosis.
        await page.locator('#triage-hazard').select_option('unknown')
        await page.set_viewport_size({'width':390,'height':844})
        await page.locator('#triage-submit').click()
        await page.locator('#triage-result .result-cause').first.wait_for()
        assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1');count+=1
        await page.screenshot(path='/mnt/data/FaultMate_AI_P72_Step3_Preview.png',full_page=True)
        assert not js_errors,js_errors
        count+=1
        await browser.close()
    print('P72_STEP3_BROWSER_PASS',count,'checks; js_errors',len(js_errors))

if __name__=='__main__':
    asyncio.run(run())
