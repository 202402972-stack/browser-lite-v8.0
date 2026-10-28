"""Small in-process watchdog: observe, preserve progress, stop without replaying actions."""
import asyncio,shutil,time
from resources import container_memory

async def shutdown_browser(browser,timeout=10):
    """Bound upstream cleanup; force only this local session's owned process tree."""
    cleanup=asyncio.create_task(browser.kill())
    done,_=await asyncio.wait([cleanup],timeout=timeout)
    if done:
        try:cleanup.result();return True
        except Exception:pass
    cleanup.cancel()
    def consumed(task):
        if not task.cancelled():task.exception()
    cleanup.add_done_callback(consumed)
    watchdog=getattr(browser,'_local_browser_watchdog',None)
    process=getattr(watchdog,'_subprocess',None)
    if process is not None:
        def terminate_owned():
            import psutil
            try:
                targets=process.children(recursive=True)+[process]
                for target in targets:
                    try:target.terminate()
                    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
                _,alive=psutil.wait_procs(targets,timeout=2)
                for target in alive:
                    try:target.kill()
                    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        await asyncio.to_thread(terminate_owned)
    bus=getattr(browser,'event_bus',None)
    if bus:
        try:await asyncio.wait_for(bus.stop(clear=True,timeout=2),3)
        except Exception:pass
    return False

class RuntimeGuard:
    def __init__(self,engine):
        self.engine=engine;self.pressure_samples=0;self.browser_failures=0;self.checks=0
        self.last_check=None;self.last_error=None;self.peak_memory=0;self.low_quality=False
    def public(self):
        used,limit=container_memory()
        return {'checks':self.checks,'last_check':self.last_check,'diagnostic':self.last_error,
                'working_set_bytes':used,'memory_limit_bytes':limit,'peak_sampled_bytes':self.peak_memory,
                'reduced_stream_quality':self.low_quality,'frames_captured':self.engine.frames_captured,'closing':self.engine.closing}
    async def tick(self):
        e=self.engine
        if e.closing:return
        self.checks+=1;self.last_check=time.time()
        job=e.job;active=bool(job and not job.done());reason=None
        if not await asyncio.to_thread(e.store.probe):reason=('STORAGE_UNAVAILABLE','تعذر حفظ التقدم؛ توقفت المهمة. راجع مساحة وصلاحيات الـVolume قبل الاستكمال.')
        elif shutil.disk_usage(e.store.root).free<64*1024**2:reason=('DISK_PRESSURE','مساحة التخزين قربت تنتهي؛ التقدم محفوظ. وفّر مساحة ثم استكمل.')
        used,limit=container_memory();self.peak_memory=max(self.peak_memory,used or 0)
        fraction=used/limit if used is not None and limit else 0
        if fraction>=.85:self.low_quality=True
        elif fraction<.75:self.low_quality=False
        self.pressure_samples=self.pressure_samples+1 if fraction>=.92 else 0
        if self.pressure_samples>=3:reason=('MEMORY_PRESSURE','الذاكرة مرتفعة باستمرار؛ حفظنا التقدم وأغلقنا المتصفح. استكمل على صفحة أخف أو موارد أكبر.')
        browser=e.browser
        if browser and active and reason is None:
            try:
                if not browser.is_cdp_connected:raise ConnectionError()
                await asyncio.wait_for(browser.get_current_page_url(),3)
                self.browser_failures=0
            except asyncio.CancelledError:raise
            except Exception:self.browser_failures+=1
            if self.browser_failures>=3:reason=('BROWSER_UNRESPONSIVE','المتصفح لا يستجيب؛ حفظنا التقدم وأوقفنا المهمة. اضغط استكمال لإعادة فتحه وفحص الصفحة.')
        else:self.browser_failures=0
        self.last_error=reason[0] if reason else None
        if active and reason:
            try:await e.pause(reason=reason,expected_job=job)
            except Exception:
                # The task was cancelled before any attempted diagnostic write.
                # A failed disk cannot be promised a new persisted checkpoint.
                e.last_failure={'stage':'maintenance','code':'STORAGE_UNAVAILABLE'}
                if e.task:e.task.update(status='paused',message=reason[1],diagnostic=e.last_failure)
                await e.close_browser()

class LoopGuard:
    """Bound identical mutations on an unchanged observable page; no parameters saved."""
    def __init__(self,engine):
        import secrets
        self.engine=engine;self.key=secrets.token_bytes(32);self.last=None;self.count=0;self.refresh_requested=False
    async def before(self,name,params):
        e=self.engine
        if not e.browser or e.verification.active or name not in {'click','input','scroll','send_keys','select_dropdown','write_editor'}:return None
        try:
            session=await asyncio.wait_for(e.browser.get_or_create_cdp_session(),2)
            response=await asyncio.wait_for(session.cdp_client.send.Runtime.evaluate(params={'expression':"(()=>{if(document.querySelector('canvas'))return null;return [location.href,document.title,document.body?.innerText.slice(0,16000),document.scrollingElement?.scrollTop,document.scrollingElement?.scrollLeft,[...document.querySelectorAll('input:not([type=password]),textarea,select')].slice(0,100).map(e=>[e.value,e.checked])];})()",'returnByValue':True},session_id=session.session_id),2)
            observed=response.get('result',{}).get('value')
            if observed is None:return None
        except asyncio.CancelledError:raise
        except Exception:return None
        import hashlib,hmac,json
        signature=hmac.new(self.key,json.dumps([name,params,observed],sort_keys=True,ensure_ascii=False).encode(),hashlib.sha256).digest()
        if signature!=self.last:
            self.last=signature;self.count=1;self.refresh_requested=False;return None
        self.count+=1
        if self.count<=3:return None
        if not self.refresh_requested:
            self.refresh_requested=True
            e.event('reading','الإجراء تكرر دون تغيير؛ يعيد قراءة الصفحة قبل محاولة أخرى')
            return 'The same action made no observable progress. Inspect the fresh page and choose a different approach; do not repeat blindly.'
        e.stop_reason=('NO_PROGRESS','الإجراء تكرر دون تغيير حتى بعد إعادة الفحص؛ حفظنا التقدم. راجع الصفحة أو وجّه المهمة ثم استكمل.')
        if e.agent:e.agent.stop()
        return 'Stopped because repeated identical mutations made no observable progress. No new mutation was executed.'
