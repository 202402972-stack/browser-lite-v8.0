"""Real archived-event pagination UI; fixture content is labeled, no inference."""
import asyncio,json,os
from pathlib import Path
from playwright.async_api import async_playwright
BASE=os.getenv('TEST_BASE_URL','http://127.0.0.1:8785')
OUT=Path(os.getenv('TEST_OUTPUT_DIR','.'))
async def main():
 OUT.mkdir(parents=True,exist_ok=True)
 async with async_playwright() as p:
  browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(BASE);await page.locator('#password').fill(os.getenv('TEST_APP_PASSWORD','minimal-testing-password'));await page.locator('#loginForm button').click();await page.locator('#loginDialog').wait_for(state='hidden')
  task=await page.evaluate("async()=>await(await fetch('/__test/archive',{method:'POST',headers:{'X-CSRF-Token':csrf}})).json()")
  await page.wait_for_function('(id)=>lastState?.task?.id===id',arg=task['id'])
  assert await page.locator('#eventCount').text_content()=='200'
  await page.locator('#toolsOpen').click();await page.locator('#historyOpen').click()
  await page.locator('#loadOlderEvents').click()
  await page.wait_for_function("()=>document.getElementById('eventCount').textContent==='240'")
  assert not await page.locator('#loadOlderEvents').is_visible()
  assert await page.locator('#activityList li').count()==240
  await page.screenshot(path=str(OUT/'preview-v75-archive.png'))
  assert 'حدث أرشيف اختبار 1' in await page.locator('#activityList li').first.text_content()
  old=await page.evaluate('(id)=>fetch("/api/tasks/"+id+"/messages?limit=100").then(r=>r.json())',task['id'])
  assert len(old['messages'])==60 and len(await page.locator('.chat-message').all())==50
  await page.locator('#activityClose').click()
  await page.locator('#loadOlderMessages').click()
  await page.wait_for_function("()=>document.querySelectorAll('.chat-message').length===60")
  assert await page.locator('.edit-message:visible').count()==50
  assert not await page.locator('#loadOlderMessages').is_visible()
  assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
  assert not errors,errors
  print(json.dumps({'archive_events':240,'initial_window':200,'archived_messages':60,'loaded_messages':60,'editable_recent_messages':50,'mobile_overflow':False,'js_errors':errors}))
  await browser.close()
asyncio.run(main())
