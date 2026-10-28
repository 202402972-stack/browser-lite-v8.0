"""Test-only fixture routes. Excluded from Docker and never imported in production."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi import Depends
import app,uvicorn

@app.app.post('/__test/target',dependencies=[Depends(app.owner)])
async def target():
    session=await app.engine.browser.get_or_create_cdp_session()
    expression="""document.documentElement.style.cssText='margin:0;padding:0';document.body.style.cssText='margin:0;background:#e8e2d4;width:100vw;height:100vh;overflow:hidden';document.body.innerHTML='<div style="position:fixed;left:0;top:0;bottom:0;width:10%;background:#ce785e"></div><div style="position:fixed;right:0;top:0;bottom:0;width:10%;background:#302c27"></div><button id="target" style="position:absolute;left:590px;top:260px;width:100px;height:80px">target</button>';window.__hits=0;document.getElementById('target').onclick=()=>window.__hits++"""
    await session.cdp_client.send.Runtime.evaluate(params={'expression':expression},session_id=session.session_id)
    return {'ok':True}
@app.app.get('/__test/metrics',dependencies=[Depends(app.owner)])
async def metrics():
    session=await app.engine.browser.get_or_create_cdp_session()
    result=await session.cdp_client.send.Runtime.evaluate(params={'expression':'JSON.stringify({hits:window.__hits||0,innerWidth,innerHeight,screenWidth:screen.width,dpr:devicePixelRatio})','returnByValue':True},session_id=session.session_id)
    import json
    return json.loads(result['result']['value'])
@app.app.post('/__test/verification',dependencies=[Depends(app.owner)])
async def verification_fixture(mode:str='simple'):
    import asyncio,time,uuid
    e=app.engine
    if e.job and not e.job.done():await e.pause()
    await e.navigate('https://example.com')
    session=await e.browser.get_or_create_cdp_session()
    click_script="this.setAttribute('aria-checked','true');window.fixtureClicks++;this.textContent='✓';setTimeout(()=>{document.querySelector('[name=g-recaptcha-response]').value='local-fixture-response';document.getElementById('outcome').textContent='Local fixture accepted'},4000)"
    import json
    body='<main style="margin:80px auto;width:620px;padding:38px;background:#e8e2d4;border-radius:24px;color:#24211e;font:24px system-ui"><small style="font-size:17px">LOCAL TEST FIXTURE · NOT A REAL CAPTCHA</small><h1 style="font-size:34px">Verification interaction test</h1><div class="g-recaptcha" style="display:flex;align-items:center;gap:20px;padding:22px;background:#fff8;border:1px solid #28242024;border-radius:16px"><button type="button" id="recaptcha-anchor" role="checkbox" aria-checked="false" style="width:50px;height:50px;font:28px system-ui;border:1px solid #777;background:white;border-radius:8px"></button><span>Check the local test box</span></div><textarea name="g-recaptcha-response" style="display:none"></textarea><p id="outcome" style="font-size:19px">Waiting for local UI check</p><button id="manualComplete" style="font:22px system-ui;padding:14px">Complete local fixture</button></main>'
    document='<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;width:100%;min-height:100vh;background:#161412}*{box-sizing:border-box}</style></head><body>'+body+'</body></html>'
    expression='document.open();document.write('+json.dumps(document)+');document.close();window.fixtureClicks=0;document.getElementById("recaptcha-anchor").onclick=function(){'+click_script+'};document.getElementById("manualComplete").onclick=()=>{document.querySelector("[name=g-recaptcha-response]").value="local-fixture-response";document.getElementById("outcome").textContent="Local fixture accepted"}'
    if mode=='complex':expression+=';document.getElementById("recaptcha-anchor").remove()'
    await session.cdp_client.send.Runtime.evaluate(params={'expression':expression},session_id=session.session_id)
    now=time.time();e.task={'id':uuid.uuid4().hex,'url':'https://example.com','status':'running','allow_actions':True,'created':now,'steps':0,'messages':[{'id':'fixture-owner','role':'user','content':'اختبار محلي للتعامل مع واجهة التحقق — ليس CAPTCHA حقيقيًا.','time':now}],'events':[]}
    original_active=e.models.active
    e.models.active=lambda:{'vision':False,'api_key':'','provider':'fixture','model':'fixture','base_url':''}
    e.verification.attempted.clear()
    async def work():
        try:
            await asyncio.sleep(1)
            await e.verification.start()
            await e.verification.guard()
            e.chat('assistant','اكتمل اختبار الواجهة المحلي؛ ده ليس إثبات حل CAPTCHA حقيقي.')
            e.update(status='completed',pending=None)
        finally:
            await e.verification.stop()
            e.models.active=original_active
    e.job=asyncio.create_task(work())
    return {'ok':True}

@app.app.get('/__test/verification/metrics',dependencies=[Depends(app.owner)])
async def verification_metrics():
    session=await app.engine.browser.get_or_create_cdp_session()
    r=await session.cdp_client.send.Runtime.evaluate(params={'expression':'JSON.stringify({clicks:window.fixtureClicks,button:(()=>{const r=document.getElementById("manualComplete").getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()})','returnByValue':True},session_id=session.session_id)
    import json
    return json.loads(r['result']['value'])

@app.app.post('/__test/archive',dependencies=[Depends(app.owner)])
async def archive_fixture():
    import uuid,time
    e=app.engine
    if e.job and not e.job.done():await e.pause()
    e.task={'id':uuid.uuid4().hex,'created':time.time(),'status':'paused','instruction':'أرشيف واجهة اختبار','steps':0}
    for n in range(240):e.event('reading','حدث أرشيف اختبار '+str(n+1))
    for n in range(60):e.chat('user','رسالة أرشيف اختبار '+str(n+1))
    return {'id':e.task['id']}

if __name__=='__main__':uvicorn.run(app.app,host='127.0.0.1',port=8785,access_log=False)
