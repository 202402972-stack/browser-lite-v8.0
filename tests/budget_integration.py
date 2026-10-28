"""Real Chromium with deterministic inference: pause at a usage cap, then resume."""
import asyncio,tempfile,json
from engine import Engine
from store import Store
from usage import normalized_usage
from browser_use.llm.views import ChatInvokeCompletion

class Model:
    model='usage-fixture';provider='test';name=model;model_name=model;_verified_api_keys=True
    calls=0
    async def ainvoke(self,messages,output_format=None,**kwargs):
        self.calls+=1
        action={'find_elements':{'selector':'a','attributes':['href'],'max_results':1}} if self.calls==1 else {'done':{'text':'Budget resume integration passed','success':True}}
        payload={'evaluation_previous_goal':'Inspected current page','memory':'Local QA','next_goal':'Inspect result then finish','action':[action]}
        return ChatInvokeCompletion(completion=output_format.model_validate(payload),usage=normalized_usage({'input_tokens':100,'output_tokens':20}))

async def main():
    with tempfile.TemporaryDirectory() as d:
        e=Engine(Store(d));model=Model();e.llm=lambda:model
        try:
            await e.start('https://example.com','Inspect the page',limits={'token_limit':50})
            await asyncio.wait_for(e.job,90)
            assert e.task['status']=='paused',e.task
            assert e.task['diagnostic']['code']=='BUDGET_PAUSED'
            assert model.calls==1 and e.usage.public()['total_tokens']==120
            e.update(limits={'token_limit':500})
            await e.resume();await asyncio.wait_for(e.job,90)
            assert e.task['status']=='completed' and model.calls==2,e.task
            assert Store(d).latest()['usage']['total_tokens']==240
            print(json.dumps({'paused_at_limit':True,'no_extra_inference_before_resume':True,'resume_completed':True,'reported_tokens':240}))
        finally:await e.close()

asyncio.run(main())
