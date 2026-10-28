import asyncio,json
import pytest
from browser_use import Tools
from browser_use.agent.views import ActionResult
from engine import Engine,SafeTools
from store import Store

def test_restart_keeps_checkpoint_and_marks_only_unfinished_action_uncertain(tmp_path):
    e=Engine(Store(tmp_path));e.task={'id':'restore','status':'running','steps':0,'instruction':'continue'}
    completed=e.progress.begin('click','النقر على عنصر في الصفحة');e.progress.finish(completed,True)
    e.progress.checkpoint(7,'Check the result, then finish','https://example.com/result')
    unfinished=e.progress.begin('input','الكتابة في حقل')
    restored=Engine(Store(tmp_path))
    assert restored.task['status']=='paused' and restored.task['steps']==7
    p=restored.task['progress']
    assert p['next_goal']=='Check the result, then finish'
    assert p['url']=='https://example.com/result'
    assert [a['status'] for a in p['actions']]==['reported_success','uncertain']
    assert p['actions'][-1]['id']==unfinished
    assert Store(tmp_path).latest()['progress']==p
    context=restored.progress.context()
    assert 'Never replay' in context and 'CURRENT page' in context and 'uncertain' in context

def test_restart_persists_pause_and_uncertainty_together(tmp_path,monkeypatch):
    store=Store(tmp_path);e=Engine(store)
    e.task={'id':'atomic-recovery','status':'running','steps':0}
    e.progress.begin('click','action under way')
    saves=[];original=store.save
    def capture(task):
        saves.append(json.loads(json.dumps(task)))
        return original(task)
    monkeypatch.setattr(store,'save',capture)
    restored=Engine(store)
    assert restored.task['status']=='paused'
    assert saves[0]['status']=='paused'
    assert saves[0]['progress']['actions'][0]['status']=='uncertain'
    assert store.latest()['progress']['review_required'] is True

def test_restart_repairs_inflight_action_in_already_paused_task(tmp_path):
    store=Store(tmp_path);e=Engine(store)
    e.task={'id':'older-shutdown','status':'paused','steps':0}
    identifier=e.progress.begin('click','action under way')
    restored=Engine(store)
    assert restored.task['status']=='paused'
    action=restored.task['progress']['actions'][0]
    assert action['id']==identifier and action['status']=='uncertain'
    assert store.latest()['progress']['review_required'] is True
    assert 'Never replay' in restored.progress.context()

def test_resume_repairs_inflight_journal_without_a_process_restart(tmp_path,monkeypatch):
    async def run():
        store=Store(tmp_path);e=Engine(store)
        e.task={'id':'resume-with-inflight','status':'paused','steps':0}
        identifier=e.progress.begin('click','action under way')
        launched=[]
        def launch():
            saved=store.latest()
            launched.append(saved)
            assert saved['status']=='starting'
            assert saved['progress']['review_required'] is True
            assert saved['progress']['actions'][-1]['id']==identifier
            assert saved['progress']['actions'][-1]['status']=='uncertain'
        monkeypatch.setattr(e,'_launch',launch)
        await e.resume()
        assert len(launched)==1
        assert 'آخر خطوة' in e.task['message']
        assert 'Never replay' in e.progress.context()
    asyncio.run(run())

@pytest.mark.parametrize('failed_save', [1, 2])
def test_resume_save_failure_can_retry_without_losing_uncertain_action(tmp_path,monkeypatch,failed_save):
    async def run():
        store=Store(tmp_path);e=Engine(store)
        e.task={'id':'resume-save-failure','status':'paused','steps':0}
        e.progress.begin('click','action under way')
        original=store.save;calls=0;launched=[]
        def fail_once(task):
            nonlocal calls
            calls+=1
            if calls==failed_save:raise OSError('temporary storage failure')
            return original(task)
        monkeypatch.setattr(store,'save',fail_once)
        monkeypatch.setattr(e,'_launch',lambda:launched.append(store.latest()))
        with pytest.raises(OSError):await e.resume()
        assert not launched and e.task['status']=='paused'
        await e.resume()
        assert len(launched)==1
        assert launched[0]['progress']['actions'][0]['status']=='uncertain'
        assert launched[0]['progress']['review_required'] is True
    asyncio.run(run())

def test_cancelled_tool_keeps_durable_uncertain_intent_without_values(tmp_path,monkeypatch):
    async def run():
        e=Engine(Store(tmp_path));e.task={'id':'interrupted','status':'running','allow_actions':True}
        tools=SafeTools(e);Action=tools.registry.create_action_model();started=asyncio.Event()
        async def interrupted(self,action,*args,**kwargs):
            persisted=Store(tmp_path).latest()['progress']['actions'][-1]
            assert persisted['status']=='in_flight'
            started.set();await asyncio.Future()
        monkeypatch.setattr(Tools,'act',interrupted)
        job=asyncio.create_task(tools.act(Action(input={'index':1,'text':'private-field-value'}),None))
        await started.wait();job.cancel();await asyncio.gather(job,return_exceptions=True)
        saved=Store(tmp_path).latest()
        assert saved['progress']['actions'][-1]['status']=='uncertain'
        assert 'private-field-value' not in json.dumps(saved)
    asyncio.run(run())

def test_tool_success_is_recorded_as_report_not_site_confirmation(tmp_path,monkeypatch):
    async def run():
        e=Engine(Store(tmp_path));e.task={'id':'success','status':'running'}
        tools=SafeTools(e);Action=tools.registry.create_action_model()
        async def success(self,action,*args,**kwargs):return ActionResult(extracted_content='private-result')
        monkeypatch.setattr(Tools,'act',success)
        await tools.act(Action(scroll={'down':True,'pages':1}),None)
        data=Store(tmp_path).latest()['progress']
        assert data['actions'][0]['status']=='reported_success'
        assert isinstance(data['actions'][0]['elapsed_ms'],int)
        assert 'private-result' not in json.dumps(data)
    asyncio.run(run())

def test_legacy_resume_and_old_uncertainty_survive_history_compaction(tmp_path):
    e=Engine(Store(tmp_path));e.task={'id':'legacy','status':'paused','steps':4,'summary':'old summary'}
    assert 'old summary' in e.progress.context()
    e.progress.begin('click','old unresolved')
    for _ in range(105):
        identifier=e.progress.begin('scroll','scroll');e.progress.finish(identifier,True)
    restored=Engine(Store(tmp_path))
    assert len(restored.task['progress']['actions'])<=102
    assert 'old unresolved' in restored.progress.context()

def test_live_view_disconnect_does_not_cancel_task(tmp_path,monkeypatch):
    import app as application
    from fastapi import WebSocketDisconnect
    class Browser:
        async def get_current_page_url(self):return 'https://example.com'
    class Socket:
        closed=False
        async def accept(self):pass
        async def send_json(self,data):pass
        async def send_bytes(self,data):raise WebSocketDisconnect()
        async def close(self):self.closed=True
    async def run():
        e=Engine(Store(tmp_path));e.task={'id':'background','status':'running'}
        e.browser=Browser()
        async def snapshot():return b'image'
        e.snapshot=snapshot;e.job=asyncio.create_task(asyncio.sleep(60))
        monkeypatch.setattr(application,'engine',e)
        monkeypatch.setattr(application,'same_origin',lambda ws:True)
        monkeypatch.setattr(application,'authenticate',lambda ws:{})
        socket=Socket()
        try:
            await asyncio.wait_for(application.live(socket),2)
            assert socket.closed and not e.job.done()
            assert e.task['status']=='running'
        finally:
            e.job.cancel();await asyncio.gather(e.job,return_exceptions=True)
    asyncio.run(run())
