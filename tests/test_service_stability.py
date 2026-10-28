import asyncio,json,sqlite3,time
from types import SimpleNamespace
import pytest
from store import Store,StoreUnavailable
from engine import Engine,SafeTools
from browser_use import Tools
from browser_use.agent.views import ActionResult
from service_runtime import shutdown_browser

def test_batch_deadline_distinguishes_an_inner_step_timeout():
    from engine import run_with_task_deadline,TaskDeadlineExceeded
    async def run():
        async def inner_timeout():raise TimeoutError('inner operation')
        with pytest.raises(TimeoutError) as caught:
            await run_with_task_deadline(inner_timeout(),10)
        assert not isinstance(caught.value,TaskDeadlineExceeded)
        with pytest.raises(TaskDeadlineExceeded):
            await run_with_task_deadline(asyncio.sleep(1),.01)
    asyncio.run(run())

def test_unfinished_run_distinguishes_failures_stop_and_step_limit():
    from engine import incomplete_reason
    settings=SimpleNamespace(max_failures=3)
    assert incomplete_reason(SimpleNamespace(state=SimpleNamespace(consecutive_failures=4,stopped=False),settings=settings))[0]=='AGENT_FAILURES'
    assert incomplete_reason(SimpleNamespace(state=SimpleNamespace(consecutive_failures=0,stopped=True),settings=settings))[0]=='AGENT_STOPPED'
    assert incomplete_reason(SimpleNamespace(state=SimpleNamespace(consecutive_failures=0,stopped=False),settings=settings))[0]=='STEP_LIMIT'

def test_legacy_migration_backup_and_archive_survive_ui_truncation(tmp_path):
    task={'id':'old','status':'paused','steps':7,'events':[{'seq':i,'kind':'step','title':str(i),'time':i} for i in range(1,251)],'messages':[{'id':str(i),'role':'user','content':str(i)} for i in range(1,56)]}
    db=sqlite3.connect(tmp_path/'tasks.sqlite3');db.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY,updated REAL,data TEXT)');db.execute('INSERT INTO tasks VALUES(?,?,?)',('old',1,json.dumps(task)));db.commit();db.close()
    store=Store(tmp_path);saved=store.latest()
    assert len(saved['events'])==200 and saved['events'][0]['seq']==51
    assert len(saved['messages'])==50 and saved['steps']==7
    backup=sqlite3.connect(tmp_path/'tasks.pre-v75.sqlite3')
    assert backup.execute('PRAGMA user_version').fetchone()[0]==0
    assert len(json.loads(backup.execute('SELECT data FROM tasks').fetchone()[0])['events'])==250
    backup.close()
    saved['messages'][0]['content']='edited';store.save(saved);store.save(saved)
    assert len(store.events('old',limit=500)['events'])==250
    all_messages=store.messages('old',limit=100)['messages'];assert len(all_messages)==55
    assert next(m for m in all_messages if m['id']==saved['messages'][0]['id'])['content']=='edited'
    raw=json.loads(store.db.execute('SELECT data FROM tasks').fetchone()[0]);assert 'events' not in raw and 'messages' not in raw
    assert store.events('old',after=200,limit=20)['next_after']==220
    page=store.events('old',before=201,limit=20)
    assert [e['seq'] for e in page['events']]==list(range(181,201)) and page['next_before']==181
    before=store.messages('old',limit=10);assert before['has_more']
    older=store.messages('old',before=before['next_before'],limit=100);assert len(older['messages'])==45

def test_archive_write_is_atomic_and_failure_does_not_echo_sql_or_paths(tmp_path,monkeypatch):
    store=Store(tmp_path);task={'id':'atomic','status':'paused','events':[{'seq':1,'title':'one'}]};store.save(task)
    old_revision=task['_revision'];original=store._archive
    def fail(*args):raise sqlite3.OperationalError('private database path and SQL')
    monkeypatch.setattr(store,'_archive',fail);task['status']='running'
    with pytest.raises(StoreUnavailable) as error:store.save(task)
    assert 'private' not in str(error.value)
    assert store.get('atomic')['status']=='paused' and store.get('atomic')['_revision']==old_revision
    assert not store.last_error is None
    monkeypatch.setattr(store,'_archive',original)
    assert store.probe() and store.last_error is None

def test_full_event_archive_keeps_sequences_after_restart(tmp_path):
    e=Engine(Store(tmp_path));e.task={'id':'history','status':'paused'}
    for n in range(240):e.event('reading',str(n))
    restored=Engine(Store(tmp_path));restored.event('reading','next')
    assert restored.task['events'][-1]['seq']==241 and len(restored.task['events'])==200
    assert len(restored.store.events('history',limit=500)['events'])==241

class Browser:
    is_cdp_connected=True
    def __init__(self):self.calls=0;self.qualities=[];self.killed=False
    async def take_screenshot(self,**kwargs):
        self.calls+=1;self.qualities.append(kwargs['quality']);await asyncio.sleep(.01);return b'jpeg'
    async def get_current_page_url(self):return 'https://example.com'
    async def kill(self):self.killed=True

def test_concurrent_viewers_share_one_frame_and_layout_invalidates_it(tmp_path):
    async def run():
        e=Engine(Store(tmp_path));b=Browser();e.browser=b
        async def metrics():pass
        e.ensure_metrics=metrics
        frames=await asyncio.gather(*[e.snapshot() for _ in range(8)])
        assert frames==[b'jpeg']*8 and b.calls==1
        e.viewport['height']=1000;await e.snapshot();assert b.calls==2
        e._frame_at-=3;e.runtime.low_quality=True;await e.snapshot();assert b.qualities[-1]==40
        await e.close_browser();assert e._frame is None and e.browser is None and b.killed
    asyncio.run(run())

def test_watchdog_sustained_memory_pressure_pauses_once_and_preserves_progress(tmp_path,monkeypatch):
    monkeypatch.setattr('service_runtime.container_memory',lambda:(950,1000))
    async def run():
        e=Engine(Store(tmp_path));e.task={'id':'pressure','status':'running','steps':7};e.progress.checkpoint(7,'continue','https://example.com')
        e.browser=Browser();e.job=asyncio.create_task(asyncio.sleep(60))
        await e.runtime.tick();await e.runtime.tick();assert not e.job.done() and e.runtime.low_quality
        await e.runtime.tick();assert e.job.done() and e.browser is None
        assert e.task['diagnostic']['code']=='MEMORY_PRESSURE' and e.task['status']=='paused'
        assert e.store.latest()['progress']['step']==7
        events=len(e.task['events']);await e.runtime.tick();assert len(e.task['events'])==events
    asyncio.run(run())

def test_watchdog_three_browser_failures_and_no_storage_write(tmp_path,monkeypatch):
    monkeypatch.setattr('service_runtime.container_memory',lambda:(1,1000))
    async def run():
        e=Engine(Store(tmp_path));e.task={'id':'browser-fault','status':'running'};e.browser=Browser();e.browser.is_cdp_connected=False
        e.job=asyncio.create_task(asyncio.sleep(60))
        for _ in range(3):await e.runtime.tick()
        assert e.task['diagnostic']['code']=='BROWSER_UNRESPONSIVE' and e.browser is None
        e.task={'id':'disk-fault','status':'running'};e.store.save(e.task);e.job=asyncio.create_task(asyncio.sleep(60))
        monkeypatch.setattr(e.store,'probe',lambda:False)
        await e.runtime.tick()
        assert e.job.done() and e.task['diagnostic']['code']=='STORAGE_UNAVAILABLE'
    asyncio.run(run())

def test_shutdown_bounds_hung_cleanup_without_global_process_kills():
    class Hung:
        async def kill(self):await asyncio.Future()
    async def run():
        start=time.monotonic();assert not await shutdown_browser(Hung(),timeout=.01)
        assert time.monotonic()-start<1
    asyncio.run(run())

def test_loop_guard_requests_refresh_then_stops_without_repeating_mutation(tmp_path,monkeypatch):
    async def run():
        e=Engine(Store(tmp_path));e.task={'id':'loop','status':'running'};mutations=[]
        class Runtime:
            async def evaluate(self,**kw):return {'result':{'value':['page','unchanged']}}
        session=SimpleNamespace(session_id='test',cdp_client=SimpleNamespace(send=SimpleNamespace(Runtime=Runtime())))
        class Page:
            async def get_or_create_cdp_session(self):return session
        e.browser=Page();e.agent=SimpleNamespace(stop=lambda:mutations.append('stopped'))
        async def guard():return False
        e.verification.guard=guard
        async def act(self,*args,**kwargs):mutations.append('action');return ActionResult(extracted_content='ok')
        monkeypatch.setattr(Tools,'act',act)
        tools=SafeTools(e);Action=tools.registry.create_action_model()
        for _ in range(5):await tools.act(Action(input={'index':1,'text':'private-action-value'}),None)
        assert mutations==['action']*3+['stopped']
        assert e.stop_reason[0]=='NO_PROGRESS'
        assert 'private-action-value' not in json.dumps(e.store.latest())
    asyncio.run(run())

def test_signal_marks_closing_before_uvicorn_drains_connections():
    import signal,uvicorn
    from serve import DotServer
    engine=SimpleNamespace(closing=False)
    server=DotServer(uvicorn.Config(lambda scope,receive,send:None),engine)
    server.handle_exit(signal.SIGTERM,None)
    assert engine.closing and server.should_exit

def test_close_persists_paused_state_even_if_worker_already_cancelled(tmp_path):
    async def run():
        e=Engine(Store(tmp_path));e.task={'id':'shutdown','status':'running'}
        e.job=asyncio.create_task(asyncio.sleep(60));e.job.cancel()
        await asyncio.gather(e.job,return_exceptions=True)
        await e.close()
        assert e.store.latest()['status']=='paused'
    asyncio.run(run())

def test_background_failure_is_consumed_and_durably_paused_without_raw_error(tmp_path):
    async def run():
        e=Engine(Store(tmp_path));e.task={'id':'worker-failure','status':'running'}
        async def failure():raise RuntimeError('private-fixture-detail')
        e.run=failure;e._launch()
        await asyncio.gather(e.job,return_exceptions=True);await asyncio.sleep(0)
        saved=e.store.latest()
        assert saved['status']=='paused' and saved['diagnostic']['code']=='WORKER_FAILURE'
        assert 'private-fixture-detail' not in json.dumps(saved)
    asyncio.run(run())

def test_first_message_save_already_contains_latest_guidance(tmp_path):
    async def run():
        e=Engine(Store(tmp_path));e.task={'id':'guidance','status':'paused','instruction':'initial','latest_guidance':'old'}
        e.chat('user','initial');e.llm=lambda:object();saved=[];original=e.store.save
        def record(task):saved.append(json.loads(json.dumps(task)));return original(task)
        e.store.save=record
        async def work():await asyncio.sleep(60)
        e.run=work
        await e.message('new guidance')
        assert saved[0]['latest_guidance']=='new guidance'
        await e.pause()
    asyncio.run(run())
