"""Real agent detects repeated inference failures; no network or paid inference."""
import asyncio,json,tempfile
from engine import Engine
from store import Store
class BrokenModel:
 model='fixture';provider='fixture';name='fixture';model_name='fixture';_verified_api_keys=True
 async def ainvoke(self,*args,**kwargs):raise ValueError('fixture invalid model response')
async def main():
 with tempfile.TemporaryDirectory() as directory:
  engine=Engine(Store(directory));engine.llm=lambda:BrokenModel()
  engine.models.active=lambda:{'provider':'fixture','model':'fixture','vision':False}
  try:
   await engine.start('','Controlled repeated provider failure')
   await asyncio.wait_for(engine.job,70)
   assert engine.task['status']=='paused',engine.task
   assert engine.task['diagnostic']['code']=='AGENT_FAILURES',engine.task['diagnostic']
   assert 'حد الخطوات' not in engine.task['message']
   assert 'fixture invalid model response' not in json.dumps(engine.task)
   print(json.dumps({'repeated_failures':'AGENT_FAILURES','message_does_not_claim_step_limit':True,'raw_error_omitted':True}))
  finally:await engine.close()
asyncio.run(main())
