"""Google's documented TEST key. This is NOT a production CAPTCHA bypass test."""
import asyncio,tempfile,json
from engine import Engine
from verification import ROOT_SCAN
from store import Store
async def main():
 with tempfile.TemporaryDirectory() as d:
  e=Engine(Store(d));e.task={'id':'google-test-key','status':'running','allow_actions':True};e.models.active=lambda:{'vision':False}
  try:
   await e.navigate('https://example.com')
   session=await e.browser.get_or_create_cdp_session()
   html='<html><head><meta charset="utf-8"><style>body{margin:50px;font:20px system-ui}</style></head><body><h1>Google official TEST key — not production</h1><div class="g-recaptcha" data-sitekey="6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"></div></body></html>'
   expression='document.open();document.write('+json.dumps(html)+');document.close();const script=document.createElement("script");script.src="https://www.google.com/recaptcha/api.js";document.head.append(script)'

   await session.cdp_client.send.Runtime.evaluate(params={'expression':expression},session_id=session.session_id)
   loaded=False
   for _ in range(25):
    r=await session.cdp_client.send.Runtime.evaluate(params={'expression':'!!document.querySelector("iframe[src*=recaptcha]")','returnByValue':True},session_id=session.session_id)
    if r['result'].get('value'):loaded=True;break
    await asyncio.sleep(1)
   assert loaded,'Google test widget did not load from this environment'
   present=False
   for _ in range(20):
    scan=await e.verification.evaluate(session,ROOT_SCAN) or {}
    if scan.get('present'):
     present=True;break
    await asyncio.sleep(1)
   if not present:
    from pathlib import Path
    Path('/workspace/scratch/google-test-widget.png').write_bytes(await e.snapshot())
   assert present,'Google widget iframe did not become visible'
   await e.verification.start()
   try:await asyncio.wait_for(e.verification.guard(),25)
   except TimeoutError:pass
   print(json.dumps({'attempted_checkboxes':len(e.verification.attempted),'verification':e.task.get('verification')},ensure_ascii=False),flush=True)
   from pathlib import Path
   Path('/workspace/scratch/google-test-widget.png').write_bytes(await e.snapshot())
   r=await session.cdp_client.send.Runtime.evaluate(params={'expression':'!!document.querySelector("[name=g-recaptcha-response]")?.value','returnByValue':True},session_id=session.session_id)
   assert r['result'].get('value'), 'No provider response observed'
   print(json.dumps({'google_official_test_key':True,'provider_response_present':True,'production_captcha_solve_tested':False,'events':e.task['events']},ensure_ascii=False))
  finally:await e.verification.stop();await e.close()
asyncio.run(main())
