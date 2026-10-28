import asyncio
from pathlib import Path
from runtime_checks import browser_runtime,RuntimeDependencyError
from engine import Engine
from store import Store

def test_missing_local_browser_is_diagnosed_before_agent(tmp_path,monkeypatch):
    monkeypatch.setenv('CHROMIUM_PATH',str(tmp_path/'absent-chromium'))
    async def run():
        status,_=await browser_runtime()
        assert not status['installed'] and status['code']=='BROWSER_MISSING'
        e=Engine(Store(tmp_path/'data'));e.llm=lambda:object()
        await e.start('','test')
        await e.job
        assert e.task['status']=='failed'
        assert e.task['diagnostic']=={'stage':'browser_start','code':'BROWSER_MISSING'}
        assert 'playwright install chromium' in e.task['message']
        assert e.browser is None
        await e.close()
    asyncio.run(run())

def test_missing_file_keeps_stage_without_leaking_path(tmp_path):
    async def run():
        e=Engine(Store(tmp_path));e.llm=lambda:object()
        async def missing():raise FileNotFoundError(2,'missing','/private/path/unknown-file')
        e.ensure_browser=missing
        await e.start('','test');await e.job
        assert e.task['diagnostic']['component']=='required_file'
        assert '/private' not in e.task['message']
        await e.close()
    asyncio.run(run())
