import asyncio,tempfile
from store import Store
from engine import Engine,SafeTools
from browser_use import Tools
from browser_use.agent.views import ActionResult

def test_new_and_legacy_tasks_default_to_automation():
 from app import TaskBody
 assert TaskBody(instruction='test').allow_actions is True
 async def run():
  with tempfile.TemporaryDirectory() as d:
   e=Engine(Store(d));e.llm=lambda:object()
   async def deferred(first=False):await asyncio.sleep(60)
   e.run=deferred
   await e.start('','test');assert e.task['allow_actions'] and e.task['automation_version']==2
   await e.pause(cancel=True)
   e.task.pop('automation_version');e.task['allow_actions']=False;e.store.save(e.task)
   recovered=Engine(Store(d));assert recovered.task['allow_actions'] is True
 asyncio.run(run())

def test_auto_mutation_has_no_approval_wait(monkeypatch):
 async def run():
  with tempfile.TemporaryDirectory() as d:
   e=Engine(Store(d));e.task={'id':'auto','status':'running','allow_actions':True}
   tools=SafeTools(e);Action=tools.registry.create_action_model();calls=[]
   async def act(self,action,*args,**kwargs):calls.append(action);return ActionResult(extracted_content='ok')
   monkeypatch.setattr(Tools,'act',act)
   await asyncio.wait_for(tools.act(Action(input={'index':1,'text':'test'}),None),1)
   assert len(calls)==1 and all(x['kind']!='approval' for x in e.task['events'])
   assert e.task['status']=='running'
 asyncio.run(run())
