"""Live chat replay, paging and scroll-anchor regression with synthetic events."""
import asyncio,json,os,time
from playwright.async_api import async_playwright
BASE=os.getenv('TEST_BASE_URL','http://127.0.0.1:8785')
PASSWORD=os.getenv('TEST_APP_PASSWORD','minimal-testing-password')
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
  await page.goto(BASE);await page.locator('#password').fill(PASSWORD);await page.locator('#loginForm button').click();await page.locator('#loginDialog').wait_for(state='hidden')
  await page.evaluate('()=>{stream.onmessage=null;stream.close();stream=null;}')
  # Keep the last decoded image through a burst and a corrupt pending frame,
  # while retaining at most one displayed and one pending object URL.
  frame_result=await page.evaluate("""async()=>{
   const png=Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='),c=>c.charCodeAt(0));
   const blob=new Blob([png],{type:'image/png'}), screen=document.getElementById('screen');
   setBrowserFrame(blob);
   for(let i=0;i<100&&pendingFrame;i++)await new Promise(r=>setTimeout(r,10));
   const previous=screen.src, initial=imageURLs.has(previous);
   for(let i=0;i<300;i++)setBrowserFrame(blob);
   const retained=imageURLs.size, kept=imageURLs.has(previous);
   for(let i=0;i<100&&(pendingFrame||queuedFrame);i++)await new Promise(r=>setTimeout(r,10));
   const lastGood=screen.src;
   setBrowserFrame(new Blob(['not an image'],{type:'image/png'}));
   for(let i=0;i<100&&pendingFrame;i++)await new Promise(r=>setTimeout(r,10));
   return {initial,retained,kept,stillVisible:screen.src===lastGood&&!screen.hidden,after:imageURLs.size};
  }""")
  assert frame_result=={'initial':True,'retained':2,'kept':True,'stillVisible':True,'after':1},frame_result
  # Deliberately hold decoding while many frames arrive. The in-flight frame
  # must complete, then only the most recent queued blob should be decoded.
  slow=await page.evaluate("""async()=>{
   const Original=window.Image, screen=document.getElementById('screen'), made=[];
   class HeldImage { constructor(){made.push(this)} set src(value){this.url=value} }
   window.Image=HeldImage;
   try{
    setBrowserFrame(new Blob(['first']));const first=pendingFrame;
    for(let i=0;i<100;i++)setBrowserFrame(new Blob([String(i)]));
    const held=pendingFrame===first, bounded=imageURLs.size<=2, queued=!!queuedFrame && await queuedFrame.text()==='99';
    first.image.onload();const advanced=screen.src===first.url, second=pendingFrame;
    const latest=!!second&&second!==first&&!queuedFrame;
    second.image.onerror();const retained=screen.src===first.url&&!screen.hidden;
    setBrowserFrame(new Blob(['cancel']));setBrowserFrame(new Blob(['queued']));cancelPendingFrame();
    return {held,bounded,queued,advanced,latest,retained,cancelled:!pendingFrame&&!queuedFrame&&imageURLs.size===1};
   }finally{cancelPendingFrame();window.Image=Original}
  }""")
  assert all(slow.values()),slow
  now=time.time();event=lambda n:{'seq':n,'kind':'action','title':f'خطوة اختبار {n}','time':now+n/1000}
  calls=[]
  async def events_route(route):
   from urllib.parse import urlsplit,parse_qs
   after=int(parse_qs(urlsplit(route.request.url).query)['after'][0]);calls.append(after)
   events=[event(n) for n in range(after+1,min(after+500,800)+1)]
   await route.fulfill(json={'events':events,'has_more':after+len(events)<800,'next_after':after+len(events)})
  await page.route('**/api/tasks/gap-test/events?*',events_route)
  state={'browser_ready':False,'busy':True,'viewport':{'width':1280,'height':800},'proxy':{'enabled':False},'files':[],
   'task':{'id':'gap-test','created':now-5,'status':'running','event_seq':800,'events':[event(n) for n in range(701,801)],'messages':[{'id':'new','role':'user','content':'طلب اختبار','time':now-1}]},
   'replay':{'events':[event(n) for n in range(1,501)],'next_after':500,'has_more':True}}
  await page.evaluate('(s)=>render(s)',state)
  await page.wait_for_function('()=>historyRows.size===800 && replayPump===null',timeout=15000)
  assert calls==[500],calls
  assert await page.locator('#chatAnnouncement').text_content()==''
  assert await page.locator('.activity-message').count()==500
  seqs=await page.locator('.activity-message').evaluate_all('(els)=>els.map(e=>Number(e.dataset.eventSeq))')
  assert seqs==list(range(301,801)),(seqs[:3],seqs[-3:])
  await page.locator('#activityList li').first.evaluate('(e)=>e.dataset.retainedFixture="yes"')
  await page.evaluate('(s)=>render(s)',state)
  assert await page.locator('.activity-message').count()==500
  await page.locator('#chatScroll').evaluate('(e)=>e.scrollTop=0');await page.wait_for_timeout(150)
  assert not await page.locator('#jumpLatest').is_visible()
  anchor=page.locator('#messages > article').first
  await anchor.evaluate('(e)=>e.dataset.anchorFixture="yes"')
  anchor_top=(await anchor.bounding_box())['y']
  state['task']['messages'].insert(0,{'id':'old','role':'user','content':'رسالة أقدم محملة','time':now-100})
  await page.evaluate('(s)=>render(s)',state);await page.wait_for_timeout(150)
  assert not await page.locator('#jumpLatest').is_visible(),'Loading older history must not increment the unseen count'
  state.pop('replay');state['task']['events'].append(event(801));state['task']['event_seq']=801
  await page.evaluate('(s)=>render(s)',state);await page.wait_for_timeout(150)
  assert await page.locator('#jumpLatest').is_visible()
  assert (await page.locator('#jumpLatest').get_attribute('aria-label')).startswith('عرض آخر 1 ')
  assert await page.locator('#chatAnnouncement').text_content()=='خطوة اختبار 801'
  assert await page.locator('#activityList li').first.evaluate('(e)=>e.dataset.retainedFixture')=='yes'
  assert abs((await page.locator('[data-anchor-fixture="yes"]').bounding_box())['y']-anchor_top)<2
  # Equal-time archived messages must use their stable ordering, not timestamp alone.
  state['task']['messages'][1]['archive_cursor']=20
  await page.evaluate('(s)=>render(s)',state)
  state['task']['messages'].insert(0,{'id':'old-tie','role':'user','content':'قديم بنفس الوقت','time':now-1,'archive_cursor':19})
  await page.evaluate('(s)=>render(s)',state);await page.wait_for_timeout(150)
  assert (await page.locator('#jumpLatest').get_attribute('aria-label')).startswith('عرض آخر 1 '),'Older equal-time row must not increment unseen count'
  state['task']['messages'].append({'id':'new-tie','role':'assistant','content':'جديد بنفس الوقت','time':now-1,'archive_cursor':21})
  await page.evaluate('(s)=>render(s)',state);await page.wait_for_timeout(150)
  assert (await page.locator('#jumpLatest').get_attribute('aria-label')).startswith('عرض آخر 2 ')
  # Larger gaps are bounded to the newest 2,000 events in memory.
  big_calls=[]
  async def big_route(route):
   from urllib.parse import urlsplit,parse_qs
   after=int(parse_qs(urlsplit(route.request.url).query)['after'][0]);big_calls.append(after)
   events=[event(n) for n in range(after+1,min(after+500,3000)+1)]
   await route.fulfill(json={'events':events,'has_more':after+len(events)<3000,'next_after':after+len(events)})
  await page.route('**/api/tasks/big-gap/events?*',big_route)
  big={'browser_ready':False,'busy':True,'viewport':{'width':1280,'height':800},'proxy':{'enabled':False},'files':[],
   'task':{'id':'big-gap','status':'running','event_seq':3000,'events':[event(n) for n in range(2901,3001)],'messages':[]},
   'replay':{'events':[event(n) for n in range(1,501)],'next_after':500,'has_more':True}}
  await page.evaluate('(s)=>render(s)',big)
  await page.wait_for_function('()=>historyRows.size===2000 && replayPump===null',timeout=20000)
  assert big_calls==[1000,1500,2000,2500],big_calls
  assert await page.evaluate('()=>Math.min(...historyRows.keys())')==1001
  assert await page.locator('.activity-message').count()==500
  # Switching tasks while a replay request is pending cannot mix task history;
  # the new task's replay still starts after the old request resolves.
  waiting=asyncio.Event();release=asyncio.Event()
  async def old_route(route):
   waiting.set();await release.wait()
   await route.fulfill(json={'events':[dict(event(n),title='OLD') for n in range(501,801)],'has_more':False,'next_after':800})
  async def new_route(route):
   await route.fulfill(json={'events':[dict(event(n),title='NEW') for n in range(501,801)],'has_more':False,'next_after':800})
  await page.route('**/api/tasks/old-gap/events?*',old_route)
  await page.route('**/api/tasks/new-gap/events?*',new_route)
  def state_for(task_id,label):
   return {'browser_ready':False,'busy':True,'viewport':{'width':1280,'height':800},'proxy':{'enabled':False},'files':[],
    'task':{'id':task_id,'status':'running','event_seq':800,'events':[dict(event(n),title=label) for n in range(701,801)],'messages':[]},
    'replay':{'events':[dict(event(n),title=label) for n in range(1,501)],'next_after':500,'has_more':True}}
  await page.evaluate('(s)=>render(s)',state_for('old-gap','OLD'))
  await asyncio.wait_for(waiting.wait(),10)
  await page.evaluate('(s)=>render(s)',state_for('new-gap','NEW'))
  release.set()
  await page.wait_for_function("()=>historyTask==='new-gap' && historyRows.size===800 && replayPump===null",timeout=15000)
  assert await page.evaluate("()=>[...historyRows.values()].every(e=>e.title==='NEW')")
  # A transient archive error keeps existing rows and allows a later retry.
  retries=[]
  async def retry_route(route):
   retries.append(1)
   if len(retries)==1:
    await route.fulfill(status=503,json={'detail':'temporary fixture error'});return
   await route.fulfill(json={'events':[dict(event(n),title='RETRY') for n in range(501,801)],'has_more':False,'next_after':800})
  await page.route('**/api/tasks/retry-gap/events?*',retry_route)
  retry=state_for('retry-gap','RETRY')
  await page.evaluate('(s)=>render(s)',retry)
  await page.wait_for_function("()=>historyTask==='retry-gap' && replayPump===null && replayKey===null",timeout=10000)
  assert len(retries)==1 and await page.evaluate('()=>historyRows.size')==600
  await page.evaluate('(s)=>render(s)',retry)
  await page.wait_for_function("()=>historyTask==='retry-gap' && historyRows.size===800 && replayPump===null",timeout=10000)
  assert len(retries)==2
  assert not errors,errors
  print(json.dumps({'gap_filled_in_chat':True,'bounded_chat_events':500,'bounded_history':2000,'task_switch_during_replay':True,'retry_after_error':True,'history_nodes_retained':True,'older_history_not_new':True,'one_new_event_badge':True,'no_js_errors':True}))
  await browser.close()
asyncio.run(main())
