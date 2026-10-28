"""Observe visible verification widgets; one native checkbox attempt, no token forging."""
import asyncio,time
from urllib.parse import urlsplit
ROOT_SCAN=r'''(()=>{
 const visible=e=>{const r=e.getBoundingClientRect();const s=getComputedStyle(e);return s.display!=='none'&&s.visibility!=='hidden'&&r.width>=20&&r.height>=20&&r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth};
 const tokens=[...document.querySelectorAll('[name="g-recaptcha-response"],[name="h-captcha-response"],[name="cf-turnstile-response"]')].some(e=>!!e.value);
 const nodes=[...document.querySelectorAll('.g-recaptcha,.h-captcha,.cf-turnstile,iframe[src*="recaptcha"],iframe[src*="hcaptcha.com"],iframe[src*="challenges.cloudflare.com"]')].filter(visible);
 const gate=document.querySelector('#challenge-running,#challenge-stage,form#challenge-form');
 if(!nodes.length&&!(gate&&visible(gate)))return {present:false,tokens};
 const frames=nodes.filter(e=>e.tagName==='IFRAME').map(e=>{const r=e.getBoundingClientRect();return {url:e.src,x:r.x,y:r.y,width:r.width,height:r.height}});
 const checked=!!document.querySelector('#recaptcha-anchor[aria-checked="true"],#checkbox[aria-checked="true"]');
 const vendor=nodes.some(e=>(e.src||'').includes('hcaptcha')||e.classList.contains('h-captcha'))?'hcaptcha':nodes.some(e=>(e.src||'').includes('cloudflare')||e.classList.contains('cf-turnstile'))||gate?'turnstile':'recaptcha';
 return {present:true,vendor,frames,tokens,checked,url:location.href};
})()'''
CHECKBOX_SCAN=r'''(()=>{
 const choices=[...document.querySelectorAll('#recaptcha-anchor[role="checkbox"],#checkbox[role="checkbox"]')].filter(e=>{const r=e.getBoundingClientRect();const s=getComputedStyle(e);return r.width>=12&&r.height>=12&&s.display!=='none'&&s.visibility!=='hidden'});
 if(choices.length!==1)return null;const e=choices[0],r=e.getBoundingClientRect();
 return {x:r.x+r.width/2,y:r.y+r.height/2,width:innerWidth,height:innerHeight,checked:e.getAttribute('aria-checked')==='true',disabled:e.getAttribute('aria-disabled')==='true'};
})()'''
class VerificationController:
    def __init__(self,engine):
        self.engine=engine;self.lock=asyncio.Lock();self.watcher=None;self.active=False;self.attempted=set();self.last_key=None;self.origin=None;self.clicked_at=0;self.action_active=False;self.ai_actions=0;self.ai_started=0;self.not_present_since=0;self.revision=0;self.decision_revision=0
    async def evaluate(self,session,expression,context=None):
        params={'expression':expression,'returnByValue':True}
        if context:params['contextId']=context
        r=await session.cdp_client.send.Runtime.evaluate(params=params,session_id=session.session_id)
        return r.get('result',{}).get('value')
    def report(self,state,vendor,detail):
        key=(state,vendor,detail)
        if key==self.last_key:return
        self.last_key=key
        e=self.engine;e.event('verification',detail)
        e.update(verification={'state':state,'vendor':vendor,'detail':detail})
    async def start(self):
        self.engine.update(verification={'state':'idle','vendor':'','detail':''})
        self.last_key=None;self.active=False;self.origin=None;self.clicked_at=0;self.ai_actions=0;self.ai_started=0;self.not_present_since=0
        self.watcher=asyncio.create_task(self.watch())
    async def stop(self):
        if self.watcher:
            self.watcher.cancel();await asyncio.gather(self.watcher,return_exceptions=True);self.watcher=None
        self.active=False
    async def watch(self):
        while True:
            try:await self.scan()
            except asyncio.CancelledError:raise
            except Exception:pass  # Navigation can detach a frame; the next scan retries observation.
            await asyncio.sleep(2)
    async def candidates(self,root,scan):
        local=await self.evaluate(root,CHECKBOX_SCAN)
        if local:return [(local,None)]
        result=[]
        # Same-process frames use an isolated world; OOPIFs use their existing CDP session.
        manager=self.engine.browser.session_manager
        sessions=list(manager.get_all_sessions().values()) if manager else []
        seen_targets=set()
        for frame in scan.get('frames',[])[:4]:
            host=(urlsplit(frame['url']).hostname or '').lower()
            if not any(host==d or host.endswith('.'+d) for d in ['google.com','recaptcha.net','hcaptcha.com','cloudflare.com']):continue
            found=False
            for s in sessions:
                target=manager.get_target(s.target_id)
                if not target or target.target_type!='iframe' or s.target_id in seen_targets:continue
                try:
                    # Some Chromium/OOPIF targets report an empty TargetInfo URL.
                    # Read the frame's own location and require an exact match to
                    # the visible, allowlisted iframe before dispatching input.
                    target_url=target.url or await self.evaluate(s,'location.href')
                    if target_url!=frame['url']:continue
                    checkbox=await self.evaluate(s,CHECKBOX_SCAN)
                except Exception:continue  # Detached frame; a later scan can retry.
                if checkbox:
                    seen_targets.add(s.target_id);result.append((checkbox,frame));found=True
            if found:continue
            tree=await root.cdp_client.send.Page.getFrameTree(session_id=root.session_id)
            for child in tree.get('frameTree',{}).get('childFrames',[]):
                info=child.get('frame',{})
                if info.get('url')!=frame['url']:continue
                world=await root.cdp_client.send.Page.createIsolatedWorld(params={'frameId':info['id'],'worldName':'dot-verification'},session_id=root.session_id)
                checkbox=await self.evaluate(root,CHECKBOX_SCAN,world['executionContextId'])
                if checkbox:result.append((checkbox,frame))
        return result
    async def scan(self):
        e=self.engine
        if not e.browser or not e.task or getattr(e,'closing',False) or getattr(e,'stopping',False):return
        async with self.lock:
            root=await e.browser.get_or_create_cdp_session()
            scan=await self.evaluate(root,ROOT_SCAN) or {}
            if not scan.get('present'):
                if self.active:
                    current=await e.browser.get_current_page_url()
                    self.not_present_since=self.not_present_since or time.monotonic()
                    if scan.get('tokens') or current!=self.origin or time.monotonic()-self.not_present_since>=2:
                        self.active=False;self.revision+=1;self.report('cleared','', 'اختفت واجهة التحقق؛ يعيد فحص الموقع')
                        if e.task.get('pending',{} ) and e.task['pending'].get('name')=='verification':e.update(status='running',pending=None)
                return
            self.not_present_since=0
            vendor=scan.get('vendor','verification')
            try:boxes=await self.candidates(root,scan)
            except Exception:boxes=[]
            checked=scan.get('checked') or any(b['checked'] for b,_ in boxes)
            if scan.get('tokens') and len(boxes)<=1:
                if self.active:
                    self.active=False;self.revision+=1;self.report('cleared',vendor,'اكتمل مؤشر التحقق في الصفحة؛ يراجع الموقع')
                    if (e.task.get('pending') or {}).get('name')=='verification':e.update(status='running',pending=None)
                return
            was_active=self.active
            self.active=True;self.origin=self.origin or scan.get('url')
            if not was_active:
                self.revision+=1
                self.report('detected',vendor,'ظهر تحقق في الصفحة')
            key=(scan.get('url'),vendor)
            can_click=e.task.get('allow_actions',True) and not self.action_active and not e.input_lock.locked()
            available=[(b,f) for b,f in boxes if not b['checked'] and not b.get('disabled')]
            if len(available)==1 and key not in self.attempted and can_click:
                self.attempted.add(key);self.clicked_at=time.monotonic();box,frame=available[0]
                x,y=box['x'],box['y']
                if frame:
                    x=frame['x']+x/max(1,box['width'])*frame['width'];y=frame['y']+y/max(1,box['height'])*frame['height']
                self.report('checking',vendor,'يضغط مربع التحقق وينتظر النتيجة')
                async with e.input_lock:
                    for kind in ['mousePressed','mouseReleased']:
                        await root.cdp_client.send.Input.dispatchMouseEvent(params={'type':kind,'x':x,'y':y,'button':'left','clickCount':1},session_id=root.session_id)
                return
            if self.clicked_at and time.monotonic()-self.clicked_at<8:return
            if self.ai_available():
                self.ai_started=self.ai_started or time.monotonic()
                self.report('ai_solving',vendor,'الإيجنت يفحص التحقق باستخدام الصور وأدوات المتصفح')
                if (e.task.get('pending') or {}).get('name')=='verification':e.update(status='running',pending=None)
                return
            detail='التحقق لم يكتمل تلقائيًا؛ التحدي ظاهر في المتصفح' if e.models.active().get('vision') else 'تحدي تحقق ظاهر؛ الصور غير مفعلة للموديل الحالي'
            self.report('needs_user',vendor,detail)
            e.update(status='waiting_user',pending={'name':'verification','detail':'أكمل التحقق الظاهر في المتصفح؛ سيفحص النتيجة تلقائيًا'})
    def ai_available(self):
        return bool(self.engine.models.active().get('vision') and self.engine.task.get('allow_actions',True) and self.ai_actions<12 and (not self.ai_started or time.monotonic()-self.ai_started<180))
    async def guard(self):
        try:await self.scan()
        except asyncio.CancelledError:raise
        except Exception:
            if not self.active:return False
        blocked=self.active and not self.ai_available()
        while self.active and (not self.ai_available() or (self.clicked_at and time.monotonic()-self.clicked_at<3)):
            await asyncio.sleep(1)
            try:await self.scan()
            except asyncio.CancelledError:raise
            except Exception:continue
        return blocked
