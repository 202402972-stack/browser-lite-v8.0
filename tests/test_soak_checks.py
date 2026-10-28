import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
import asyncio
spec=importlib.util.spec_from_file_location('soak_controller',Path(__file__).with_name('soak.py'));soak=importlib.util.module_from_spec(spec);spec.loader.exec_module(soak)

def test_liveness_rejects_dead_workers_even_during_restart_grace():
 with pytest.raises(RuntimeError,match='STREAM_WORKER_STOPPED'):
  soak.check_liveness([SimpleNamespace(done=lambda:True)],[99,99],99,99,100,0,200)

@pytest.mark.parametrize('frames,event,progress,code',[
 ([None,99],99,99,'FRAME_STREAM_STALLED'),([99,99],0,99,'SSE_STREAM_STALLED'),([99,99],99,0,'TASK_PROGRESS_STALLED')])
def test_liveness_catches_missing_transport_or_progress(frames,event,progress,code):
 with pytest.raises(RuntimeError,match=code):soak.check_liveness([],frames,event,progress,100,0)

def test_liveness_allows_healthy_streams_and_explicit_restart_window():
 soak.check_liveness([],[99,99],99,99,100,0)
 soak.check_liveness([],[None,None],None,0,100,0,150)

def test_timer_waits_for_running_and_rejects_early_failure(monkeypatch):
 async def run():
  statuses=iter(['starting','running'])
  async def get(_):return {'task':{'status':next(statuses)}}
  async def fast_sleep(_):pass
  monkeypatch.setattr(soak.asyncio,'sleep',fast_sleep)
  await soak.wait_until_running(get)
  async def failed(_):return {'task':{'status':'failed'}}
  with pytest.raises(RuntimeError,match='did not enter running'):
   await soak.wait_until_running(failed)
 asyncio.run(run())
