import asyncio,json
from types import SimpleNamespace
import pytest
from pydantic import BaseModel,ValidationError
from store import Store
from engine import Engine
from usage import UsageLedger,MeteredModel,BudgetExceeded,normalized_usage
from providers import measured_completion

def config():return {'provider':'fixture','model':'m','pricing':{'input':2.,'output':4.,'cached_input':1.,'source':'fixture','checked_at':'2026-10-25'}}
def setup(tmp_path,limits=None):
    e=Engine(Store(tmp_path));e.task={'id':'usage-task','status':'running','limits':limits or {}}
    return e

def test_reported_usage_pricing_cache_and_restart(tmp_path):
    e=setup(tmp_path);c=config()
    entry=e.usage.begin(c)
    e.usage.finish(entry,normalized_usage({'prompt_tokens':1000,'completion_tokens':200,'prompt_tokens_details':{'cached_tokens':400}}),c)
    report=e.usage.public()
    assert report['total_tokens']==1200 and report['cached_tokens']==400
    assert report['estimated_cost_usd']==pytest.approx(.0024)
    restored=Engine(Store(tmp_path))
    assert restored.usage.public()['estimated_cost_usd']==report['estimated_cost_usd']
    assert report['recent'][0]['pricing']['source']=='fixture'

def test_zero_pricing_is_distinct_from_missing_pricing(tmp_path):
    e=setup(tmp_path);c=config();c['pricing']={'input':0,'output':0}
    entry=e.usage.begin(c);e.usage.finish(entry,normalized_usage({'input_tokens':20,'output_tokens':2}),c)
    assert e.usage.public()['estimated_cost_usd']==0
    c.pop('pricing');entry=e.usage.begin(c);e.usage.finish(entry,normalized_usage({'input_tokens':2,'output_tokens':2}),c)
    assert e.usage.public()['estimated_cost_usd'] is None

def test_token_limit_blocks_next_call_but_not_current_result(tmp_path):
    e=setup(tmp_path,{'token_limit':10});calls=[]
    class Model:
        async def ainvoke(self,*args,**kw):
            calls.append(True)
            return SimpleNamespace(usage=normalized_usage({'input_tokens':20,'output_tokens':4}),completion='ok')
    async def run():
        m=MeteredModel(Model(),e.usage,config())
        assert (await m.ainvoke([])).completion=='ok'
        with pytest.raises(BudgetExceeded):await m.ainvoke([])
        assert len(calls)==1
        e.task['limits']['token_limit']=100
        await m.ainvoke([])
        assert len(calls)==2
    asyncio.run(run())
    assert isinstance(e.usage.public()['recent'][-1]['elapsed_ms'],int)

def test_unreported_and_interrupted_requests_are_not_zero_and_cap_stops(tmp_path):
    e=setup(tmp_path,{'token_limit':100})
    entry=e.usage.begin(config());e.usage.finish(entry,None,config(),'failed')
    assert e.usage.public()['measurement']=='partial'
    assert e.usage.public()['estimated_cost_usd'] is None
    with pytest.raises(BudgetExceeded):e.usage.check()
    e.task['limits']={};e.usage.begin(config())  # power loss before a response
    restored=Engine(Store(tmp_path))
    assert restored.usage.public()['unknown_calls']==2

def test_validation_failure_preserves_provider_usage(tmp_path):
    class Probe(BaseModel):ok:bool
    class Model:
        async def ainvoke(self,*args,**kwargs):
            return measured_completion(Probe,'invalid-json',normalized_usage({'input_tokens':100,'output_tokens':5}))
    e=setup(tmp_path)
    async def run():
        with pytest.raises(ValidationError):await MeteredModel(Model(),e.usage,config()).ainvoke([])
    asyncio.run(run())
    assert e.usage.public()['total_tokens']==105
    assert e.usage.public()['unknown_calls']==0
    assert 'invalid-json' not in json.dumps(e.task)

def test_money_limit_and_missing_price_are_not_silently_ignored(tmp_path):
    e=setup(tmp_path,{'cost_limit_usd':.0001});entry=e.usage.begin(config())
    e.usage.finish(entry,normalized_usage({'input_tokens':1000,'output_tokens':1000}),config())
    with pytest.raises(BudgetExceeded):e.usage.check()
    assert normalized_usage({'prompt_tokens':-1,'completion_tokens':1}) is None

def test_upstream_compaction_settings_survive_agent_revalidation():
    from usage import compaction_settings
    from browser_use.agent.views import AgentSettings
    model=object();s=compaction_settings({'context_window':32768},model)
    validated=AgentSettings(message_compaction=s)
    assert validated.message_compaction.compaction_llm is model
    assert validated.message_compaction.trigger_char_count==int(32768*.7*4)

