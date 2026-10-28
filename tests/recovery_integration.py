"""Real local Chromium process loss, preserved checkpoint and explicit resume; no paid inference."""
import asyncio,tempfile,json
from engine import Engine
from store import Store
from browser_use.llm.views import ChatInvokeCompletion
from usage import normalized_usage
class Model:
 model='recovery-fixture';provider='test';name=model;model_name=model;_verified_api_keys=True
 finish=False;calls=0
 async def ainvoke(self,messages,output_format=None,**kwargs):
  self.calls+=1;await asyncio.sleep(.4)
  action={'done':{'text':'Recovery integration passed','success':True}} if self.finish else {'find_elements':{'selector':'a','attributes':['href'],'max_results':1}}
  return ChatInvokeCompletion(completion=output_format.model_validate({'evaluation_previous_goal':'Observed current page','memory':'Controlled QA','next_goal':'Inspect current page then continue','action':[action]}),usage=normalized_usage({'input_tokens':100,'output_tokens':20}))
async def main():
 with tempfile.TemporaryDirectory() as directory:
  e=Engine(Store(directory));model=Model();e.llm=lambda:model
  try:
   await e.start('https://example.com','Controlled recovery task: inspect current page')
   for _ in range(120):
    if e.task.get('steps',0)>=1:break
    if e.job.done():raise AssertionError(e.task)
    await asyncio.sleep(.25)
   assert e.task['steps']>=1
   previous=e.task['steps']
   process=e.browser._local_browser_watchdog._subprocess
   # Only kill the explicitly owned local browser processes for this test.
   import psutil
   for target in process.children(recursive=True)+[process]:
    try:target.kill()
    except psutil.NoSuchProcess:pass
   for _ in range(8):
    if e.job.done():break
    await e.runtime.tick();await asyncio.sleep(.25)
   await asyncio.wait_for(asyncio.gather(e.job,return_exceptions=True),40)
   assert e.task['status'] in ('paused','failed'),e.task
   assert e.store.latest()['progress']['step']>=previous
   interrupted=e.task.get('diagnostic')
   model.finish=True;await e.resume();await asyncio.wait_for(e.job,90)
   assert e.task['status']=='completed',e.task
   assert e.task['steps']>previous
   print(json.dumps({'owned_chromium_loss':True,'checkpoint_preserved':True,'explicit_resume_completed':True,'steps':e.task['steps'],'interruption_diagnostic':interrupted}))
  finally:await e.close()
asyncio.run(main())
