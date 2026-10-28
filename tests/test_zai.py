import asyncio,json
from types import SimpleNamespace
from pydantic import BaseModel
from browser_use.llm.messages import UserMessage,ContentPartImageParam,ImageURL
from model_settings import ModelSettings
from store import Store
from providers import ZaiModel,ObservedModel
class Probe(BaseModel):ok:bool

def test_zai_visual_preset_and_text_model_compatibility(tmp_path):
 settings=ModelSettings(Store(tmp_path))
 public=settings.public()['profiles']['zai'];assert public['vision'] is True and public['model']=='glm-4.6v-flash'
 p=settings.resolve({'provider':'zai','model':'glm-4.5-flash','api_key':'id.secret'})
 assert p['base_url']=='https://api.z.ai/api/paas/v4' and p['vision'] is False
 settings.save(p);assert settings.active()['provider']=='zai'
 assert 'id.secret' not in json.dumps(settings.public())

def test_zai_json_object_and_vision_protocol(monkeypatch):
 calls=[];closed=[]
 class Client:
  def __init__(self,**kw):
   assert kw['base_url']=='https://api.z.ai/api/paas/v4'
   self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
  async def __aenter__(self):return self
  async def __aexit__(self,*args):closed.append(True)
  async def create(self,**kw):
   calls.append(kw)
   return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}' if len(calls)==1 else '```json\n{"ok":true}\n```',reasoning_content='private reasoning'))],usage=SimpleNamespace(prompt_tokens=10,completion_tokens=3,prompt_tokens_details=SimpleNamespace(cached_tokens=2)))
 monkeypatch.setattr('openai.AsyncOpenAI',Client)
 async def run():
  m=ZaiModel('glm-4.5-flash','id.secret','https://api.z.ai/api/paas/v4')
  result=await m.ainvoke([UserMessage(content='Return JSON')],output_format=Probe)
  assert result.completion.ok
  assert result.usage.total_tokens==13 and result.usage.prompt_cached_tokens==2
  assert calls[0]['response_format']=={'type':'json_object'}
  assert calls[0]['extra_body']=={'thinking':{'type':'disabled'}}
  assert 'properties' in calls[0]['messages'][0]['content']
  vision=ZaiModel('glm-4.6v','id.secret','https://api.z.ai/api/paas/v4')
  await vision.ainvoke([UserMessage(content=[ContentPartImageParam(image_url=ImageURL(url='data:image/png;base64,AA=='))])],output_format=Probe)
  assert 'response_format' not in calls[1]
  assert len(closed)==2
 asyncio.run(run())

def test_observed_model_records_request_boundaries_without_reasoning():
 class Model:
  model='fixture';provider='test'
  async def ainvoke(self,*args,**kw):return 'result'
 events=[];m=ObservedModel(Model(),events.append)
 assert asyncio.run(m.ainvoke([]))=='result' and m.model=='fixture'
 assert len(events)==2 and 'انتظار' in events[0] and 'وصل' in events[1]

def test_json_fence_is_normalized_but_prose_is_not_guessed():
 import pytest
 from pydantic import ValidationError
 from providers import validated_json
 assert validated_json(Probe,'```json\n{"ok":true}\n```').ok
 with pytest.raises(ValidationError):validated_json(Probe,'Here is a guess: {"ok":true}')
