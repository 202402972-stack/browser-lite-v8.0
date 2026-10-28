"""Controlled local widget only: NOT proof of defeating a real CAPTCHA vendor."""
import asyncio,json,os
from pathlib import Path
from playwright.async_api import async_playwright
BASE=os.getenv('TEST_BASE_URL','http://127.0.0.1:8785');OUT=Path(os.getenv('TEST_OUTPUT_DIR','/workspace/browser-lite'))
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(BASE);await page.locator('#password').fill('minimal-testing-password');await page.locator('#loginForm button').click();await page.locator('#loginDialog').wait_for(state='hidden')
  await page.evaluate("async()=>{const r=await fetch('/__test/verification?mode=simple',{method:'POST',headers:{'X-CSRF-Token':csrf}});if(!r.ok)throw Error('fixture failed')}")
  await page.wait_for_function("()=>document.getElementById('verificationBar').dataset.state==='checking'",timeout=45000)
  await page.locator('#screen').wait_for(state='visible');await page.wait_for_timeout(700)
  await page.screenshot(path=str(OUT/'preview-verification-checking.png'))
  await page.wait_for_function("()=>lastState?.task?.status==='completed'",timeout=15000);await page.wait_for_timeout(1000)
  metrics=await page.evaluate("async()=>await(await fetch('/__test/verification/metrics')).json()")
  assert metrics['clicks']==1,metrics
  await page.screenshot(path=str(OUT/'preview-verification-complete.png'))
  await page.evaluate("async()=>{const r=await fetch('/__test/verification?mode=complex',{method:'POST',headers:{'X-CSRF-Token':csrf}});if(!r.ok)throw Error('fixture failed')}")
  await page.wait_for_function("()=>lastState?.task?.status==='waiting_user'&&manualVerification",timeout=20000);await page.wait_for_timeout(1000)
  count=await page.locator('.activity-message').count();await page.wait_for_timeout(2300);assert await page.locator('.activity-message').count()==count
  await page.screenshot(path=str(OUT/'preview-verification-needs-vision.png'))
  await page.evaluate("()=>api('control/approve',{})");await page.wait_for_timeout(200)
  assert await page.evaluate("lastState.task.status")=='waiting_user'
  metrics=await page.evaluate("async()=>await(await fetch('/__test/verification/metrics')).json()")
  rect=await page.locator('#screen').bounding_box();native=await page.locator('#screen').evaluate('(e)=>[e.naturalWidth,e.naturalHeight]')
  await page.mouse.click(rect['x']+metrics['button']['x']/native[0]*rect['width'],rect['y']+metrics['button']['y']/native[1]*rect['height'])
  await page.wait_for_function("()=>lastState?.task?.status==='completed'",timeout=10000)
  assert not errors,errors
  assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
  print(json.dumps({'local_fixture_auto_clicks':1,'no_event_flood':True,'blind_approval_rejected':True,'manual_input_while_waiting':True,'js_errors':errors,'real_vendor_solve_tested':False}))
  await b.close()
asyncio.run(main())
