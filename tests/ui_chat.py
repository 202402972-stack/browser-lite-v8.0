"""Real browser UI/security/draft regression; preview chat content is synthetic and labeled."""
import asyncio,json,time,os
from pathlib import Path
from playwright.async_api import async_playwright
BASE=os.getenv('TEST_BASE_URL','http://127.0.0.1:8785');OUT=Path(os.getenv('TEST_OUTPUT_DIR','.'))
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch();context=await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,permissions=['clipboard-read','clipboard-write']);page=await context.new_page()
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(BASE);await page.locator('#password').fill(os.getenv('TEST_APP_PASSWORD','minimal-testing-password'));await page.locator('#loginForm button').click();await page.locator('#loginDialog').wait_for(state='hidden');await page.wait_for_function('()=>authenticated&&draftRestored')
  await page.locator('#instruction').fill('مسودة عادية للبحث عن المراجع')
  await page.reload();await page.wait_for_function('()=>authenticated&&draftRestored')
  assert await page.locator('#instruction').input_value()=='مسودة عادية للبحث عن المراجع'
  # Known key shapes are never persisted as a composer draft.
  sensitive='sk-'+'Q'*30
  await page.locator('#instruction').fill(sensitive)
  assert await page.evaluate("sessionStorage.getItem('dot:composer:v1')") is None
  await page.locator('#instruction').fill('')
  await page.locator('#url').fill('https://example.com');await page.locator('#open').click();await page.locator('#screen').wait_for(state='visible',timeout=45000)
  await page.wait_for_function('()=>!document.getElementById("open").disabled',timeout=45000)
  await page.evaluate('()=>{stream.onmessage=null;stream.close();stream=null;}')
  now=time.time()
  state={'browser_ready':True,'busy':False,'viewport':{'width':1280,'height':2200},'proxy':{'enabled':False},'files':[],'task':{'id':'ui-chat-preview','created':now-30,'status':'paused','steps':3,'url':'https://example.com','messages':[{'id':'owner','role':'user','content':'راجع الصفحة وورّيني مثال بسيط.','time':now-29}],'events':[{'seq':1,'kind':'reading','title':'معاينة واجهة — رسائل تجريبية، وليست تنفيذ مهمة','time':now-28}]}}
  dangerous='''<img src=x onerror="window.__xss=1"><svg onload="window.__xss=2"></svg><iframe src="https://example.com"></iframe><form><input autofocus></form> [bad](javascript:alert(1)) <a href="javascript&#58;alert(1)">bad</a> [safe](https://example.com)\n```html\n<script>window.__xss=3</script>\n```'''
  state['task']['messages'].append({'id':'answer','role':'assistant','content':dangerous,'time':now-20})
  await page.evaluate('(s)=>render(s)',state)
  bubble=page.locator('.assistant .message-bubble')
  assert await bubble.locator('img,svg,iframe,input,form,script').count()==1  # only our copy SVG
  assert await bubble.locator('script,img,iframe,input,form').count()==0
  assert await page.evaluate('window.__xss||0')==0
  links=await bubble.locator('a').evaluate_all('(links)=>links.map(a=>({url:a.href,target:a.target,rel:a.rel}))')
  assert len(links)==1 and links[0]['url']=='https://example.com/' and links[0]['target']=='_blank' and 'noreferrer' in links[0]['rel']
  await bubble.locator('button[aria-label="نسخ الكود"]').click()
  assert '<script>window.__xss=3</script>' in await page.evaluate('navigator.clipboard.readText()')
  state['task']['messages'][-1]['content']='```js\nconst data = "'+'x'*1200+'";\n```\n\n| عمود | نتيجة |\n| --- | --- |\n| مثال | واضح |'
  await page.evaluate('(s)=>render(s)',state)
  assert await page.locator('.code-block pre').evaluate('(e)=>e.scrollWidth>e.clientWidth')
  assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
  # Edit cancellation restores the unsent text instead of discarding it.
  await page.locator('#instruction').fill('مسودتي قبل التعديل');await page.locator('.edit-message').click();await page.locator('#cancelEdit').click()
  assert await page.locator('#instruction').input_value()=='مسودتي قبل التعديل'
  await page.locator('#instruction').fill('');await page.locator('#instruction').blur()
  # Long timeline, stable node identity, no forced scroll while reading older events.
  state['task']['events'] += [{'seq':i,'kind':'action','title':f'حدث تجريبي {i}: فحص الصفحة','time':now-19+i/100} for i in range(2,42)]
  await page.evaluate('(s)=>render(s)',state);await page.wait_for_timeout(350)
  await page.locator('#chatScroll').evaluate('(e)=>e.scrollTop=0');await page.wait_for_timeout(150)
  first=page.locator('#messages > article').first;await first.evaluate('(e)=>e.dataset.identity="retained"')
  state['task']['events'].append({'seq':42,'kind':'action','title':'حدث جديد تجريبي','time':now+1})
  await page.evaluate('(s)=>render(s)',state);await page.wait_for_timeout(200)
  assert await page.locator('#chatScroll').evaluate('(e)=>e.scrollTop')<2
  assert await first.evaluate('(e)=>e.dataset.identity')=='retained'
  assert await page.locator('#jumpLatest').is_visible()
  await page.locator('#jumpLatest').click();await page.wait_for_timeout(200)
  assert await page.locator('#chatScroll').evaluate('(e)=>e.scrollHeight-e.scrollTop-e.clientHeight')<3
  # Clean labeled preview, actual example.com live image.
  # A separate fixture task prevents old synthetic events from remaining in
  # the now-persistent replay history of the earlier scrolling scenario.
  state['task']['id']='ui-chat-final-preview'
  state['task']['events']=state['task']['events'][:1]+[{'seq':2,'kind':'navigation','title':'فتح الصفحة — مثال عرض','time':now-25},{'seq':3,'kind':'reading','title':'قراءة المحتوى — مثال عرض','time':now-23}]
  state['task']['messages'][-1]['content']='الصفحة واضحة. ده مثال لتنسيق الرد، ومعاه رابط [الموقع](https://example.com).\n\n```python\nprint("Hello, dot")\n```'
  await page.evaluate('(s)=>render(s)',state);await page.evaluate('ChatView.latest()');await page.wait_for_timeout(400)
  for width in [360,390,430,768,1280]:
   await page.set_viewport_size({'width':width,'height':844});await page.wait_for_timeout(250)
   assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
   rect=await page.locator('#screen').bounding_box();assert abs(rect['x'])<1 and abs(rect['width']-width)<1
  await page.set_viewport_size({'width':390,'height':844});await page.wait_for_timeout(300)
  await page.locator('#toast').wait_for(state='hidden')
  await page.screenshot(path=str(OUT/'preview-v74-chat.png'))
  # Simulate a short visual viewport with keyboard; the server viewport must not resize.
  await page.locator('#instruction').fill('كمّل المراجعة من هنا');await page.locator('#instruction').focus()
  await page.evaluate("()=>{window.__vv=visualViewport;const v=new EventTarget();v.height=420;v.offsetTop=0;Object.defineProperty(window,'visualViewport',{configurable:true,value:v});syncViewport()}")
  await page.wait_for_timeout(250)
  assert await page.locator('#form').evaluate('(e)=>e.getBoundingClientRect().bottom')<=420
  assert await page.locator('#chatScroll').evaluate('(e)=>e.getBoundingClientRect().height')>=100
  await page.screenshot(path=str(OUT/'preview-v74-keyboard.png'),clip={'x':0,'y':0,'width':390,'height':420})
  await page.evaluate("()=>{Object.defineProperty(window,'visualViewport',{configurable:true,value:window.__vv});syncViewport()}")
  await page.locator('#instruction').fill('');await page.locator('#instruction').blur()
  await page.locator('#settingsOpen').click();await page.wait_for_timeout(400)
  assert not await page.locator('#proxySettings').evaluate('(e)=>e.open')
  await page.screenshot(path=str(OUT/'preview-v74-settings.png'))
  await page.locator('#modelName').focus()
  await page.evaluate("()=>{const v=new EventTarget();v.height=420;v.offsetTop=0;Object.defineProperty(window,'visualViewport',{configurable:true,value:v});syncViewport()}")
  bounds=await page.locator('#settings').bounding_box();assert bounds['y']>=0 and bounds['y']+bounds['height']<=421,bounds
  await page.evaluate("()=>{Object.defineProperty(window,'visualViewport',{configurable:true,value:window.__vv});syncViewport()}")
  await page.locator('#settingsClose').click()
  await page.emulate_media(reduced_motion='reduce')
  assert await page.locator('.chat-message').first.evaluate('(e)=>getComputedStyle(e).animationName')=='none'
  # All primary icon controls have full-size touch bounds.
  for selector in ['#settingsOpen','#toolsOpen','#start','.edit-message']:
   r=await page.locator(selector).first.bounding_box();assert r['width']>=44 and r['height']>=44,(selector,r)
  # A lost viewer connection retains the last image. Hiding the tab closes
  # viewer transports without sending any task pause/cancel request.
  image=await page.locator('#screen').get_attribute('src')
  await page.evaluate('()=>live.close()');await page.wait_for_timeout(150)
  assert await page.locator('#screen').get_attribute('src')==image
  assert await page.locator('#screen').is_visible()
  mutations=[];page.on('request',lambda r:mutations.append(r.url) if '/api/control/' in r.url else None)
  await page.evaluate("()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))}")
  assert await page.evaluate('live===null&&stream===null')
  await page.evaluate("()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'))}")
  await page.wait_for_function('()=>live?.readyState===1&&stream?.readyState===1')
  assert not mutations
  # Expired server session must lead back to login instead of endless reconnect.
  await page.evaluate("()=>fetch('/api/logout',{method:'POST',headers:{'X-CSRF-Token':csrf}})")
  await page.wait_for_function('()=>document.getElementById("loginDialog").open',timeout=15000)
  await page.route('**/api/session',lambda route:route.fulfill(status=503,json={'detail':'إعدادات مشفرة غير متاحة — اختبار'}))
  await page.reload()
  await page.wait_for_function('()=>document.getElementById("loginError").textContent.includes("إعدادات مشفرة")')
  assert not errors,errors
  print(json.dumps({'draft_restored':True,'known_key_not_persisted':True,'markdown_sanitized':True,'code_copy':True,'edit_cancel_restores_draft':True,'scroll_anchor_and_jump':True,'widths':[360,390,430,768,1280],'short_keyboard_and_dialog':True,'reduced_motion':True,'touch_targets':44,'expired_session_login':True,'settings_error_visible':True,'js_errors':errors,'chat_preview_is_synthetic':True}))
  await browser.close()
asyncio.run(main())
