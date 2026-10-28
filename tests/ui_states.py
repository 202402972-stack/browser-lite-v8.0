"""Capture labeled synthetic task states in the real mobile-sized UI."""
import asyncio,json,os,time
from pathlib import Path
from playwright.async_api import async_playwright
BASE=os.getenv('TEST_BASE_URL','http://127.0.0.1:8785');OUT=Path(os.getenv('TEST_OUTPUT_DIR','/workspace/scratch/ui77'))
async def main():
 OUT.mkdir(parents=True,exist_ok=True)
 async with async_playwright() as p:
  browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(BASE);await page.locator('#password').fill('minimal-testing-password');await page.locator('#loginForm button').click();await page.locator('#loginDialog').wait_for(state='hidden')
  await page.locator('#url').fill('https://example.com');await page.locator('#open').click();await page.locator('#screen').wait_for(state='visible',timeout=45000)
  await page.wait_for_function('()=>!document.getElementById("open").disabled',timeout=45000)
  await page.locator('#toast').wait_for(state='hidden',timeout=10000)
  await page.wait_for_timeout(1200)  # Let the shared JPEG cache advance after navigation.
  await page.evaluate('()=>{stream.onmessage=null;stream.close();stream=null;}')
  now=time.time();state={'browser_ready':True,'busy':True,'viewport':{'width':1280,'height':2200},'proxy':{'enabled':False},'files':[],
   'task':{'id':'states-fixture','created':now-30,'status':'running','steps':2,'url':'https://example.com',
    'messages':[{'id':'request','role':'user','content':'معاينة اختبار: اقرأ الصفحة وراجع محتواها.','time':now-29}],
    'events':[{'seq':1,'kind':'navigation','title':'فتح الصفحة — اختبار','time':now-25},{'seq':2,'kind':'reading','title':'قراءة الصفحة — اختبار','time':now-15},{'seq':3,'kind':'model','title':'انتظار رد الموديل — اختبار','time':now-3}]}}
  await page.evaluate('(s)=>render(s)',state);await page.evaluate('()=>document.fonts.ready');await page.wait_for_timeout(1000)
  await page.locator('.chat-message .message-bubble').first.inner_text()
  assert await page.locator('.activity-message').count()==3
  await page.screenshot(path=str(OUT/'preview-v77-running.png'),animations='disabled')
  state['busy']=False;state['task']['status']='paused';state['task']['events'].append({'seq':4,'kind':'paused','title':'المهمة متوقفة — اختبار','time':now+1})
  await page.evaluate('(s)=>render(s)',state);await page.wait_for_timeout(700)
  await page.locator('#toolsOpen').click();assert await page.locator('#resume').is_visible()
  await page.locator('.chat-message .message-bubble').first.inner_text()
  await page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
  await page.screenshot(path=str(OUT/'preview-v77-paused.png'),animations='disabled');await page.locator('#toolsOpen').click()
  # A disconnect must keep the previous image and must not send a task-control request.
  source=await page.locator('#screen').get_attribute('src');mutations=[]
  page.on('request',lambda r:mutations.append(r.url) if '/api/control/' in r.url else None)
  await page.evaluate('()=>{viewConnected=false;stateConnected=false;frameWaiting=true;updateConnection()}')
  assert await page.locator('#connectionNotice').is_visible()
  assert await page.locator('#screen').get_attribute('src')==source
  await page.locator('.chat-message .message-bubble').first.inner_text()
  await page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
  await page.screenshot(path=str(OUT/'preview-v77-reconnecting.png'),animations='disabled')
  assert not mutations and not errors,(mutations,errors)
  # The notice describes the viewer rather than promising task progress from
  # stale state. Never claim a saved frame if no frame is visible.
  assert 'آخر عرض محفوظ' in await page.locator('#connectionNotice').inner_text()
  await page.evaluate('()=>{stateConnected=true;viewConnected=false;frameWaiting=true;lastState.busy=true;lastState.task.status="waiting_user";updateConnection()}')
  notice=await page.locator('#connectionNotice').inner_text()
  assert 'يعيد توصيل العرض' in notice and 'المهمة مستمرة' not in notice,notice
  await page.evaluate('()=>{stateConnected=false;document.getElementById("screen").hidden=true;updateConnection()}')
  notice=await page.locator('#connectionNotice').inner_text()
  assert 'آخر عرض محفوظ' not in notice,notice
  assert not mutations and not errors,(mutations,errors)
  print(json.dumps({'synthetic_running_and_paused':True,'last_frame_retained':True,'disconnect_did_not_control_task':True,'js_errors':errors}))
  await browser.close()
asyncio.run(main())
