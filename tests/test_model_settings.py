import asyncio,json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from model_settings import ModelSettings
from store import Store,SecretUnavailable

def test_encrypted_profiles_precedence_and_restart(tmp_path,monkeypatch):
 monkeypatch.setenv('LLM_API_KEY','environment-key');monkeypatch.setenv('LLM_PROVIDER','agent_router')
 settings=ModelSettings(Store(tmp_path))
 assert settings.active()['api_key']=='environment-key'
 profile=settings.resolve({'provider':'nvidia','model':'chosen-model','api_key':'private-nvidia-key'})
 settings.save(profile)
 assert b'private-nvidia-key' not in (tmp_path/'models.enc').read_bytes()
 assert 'private-nvidia-key' not in json.dumps(settings.public())
 restored=ModelSettings(Store(tmp_path));assert restored.active()['api_key']=='private-nvidia-key'
 assert restored.resolve({'provider':'nvidia','model':'other'})['api_key']=='private-nvidia-key'
 restored.delete('nvidia');assert restored.active()['api_key']=='environment-key'

def test_missing_encryption_key_never_replaces_existing_settings(tmp_path,monkeypatch):
 monkeypatch.delenv('SETTINGS_ENCRYPTION_KEY',raising=False)
 store=Store(tmp_path);store.save_secret('models',{'api_key':'private-fixture'})
 original=(tmp_path/'models.enc').read_bytes()
 (tmp_path/'settings.key').unlink()
 with pytest.raises(SecretUnavailable):store.secret('models')
 with pytest.raises(SecretUnavailable):store.save_secret('proxy',{'enabled':True})
 assert not (tmp_path/'settings.key').exists()
 assert (tmp_path/'models.enc').read_bytes()==original and not (tmp_path/'proxy.enc').exists()

def test_corrupt_encrypted_settings_return_safe_recovery_message(client):
 c,e=client
 path=e.models.store.root/'models.enc'
 path.write_bytes(b'corrupt-private-test')
 response=c.get('/api/model/settings')
 assert response.status_code==503 and response.json()['code']=='SETTINGS_UNAVAILABLE'
 assert 'corrupt-private-test' not in response.text

@pytest.fixture
def client(tmp_path,monkeypatch):
 import app
 monkeypatch.setenv('APP_PASSWORD','unit-testing-password')
 monkeypatch.setattr(app.engine,'models',ModelSettings(Store(tmp_path)))
 async def valid(url,**kwargs):return url
 monkeypatch.setattr('network.validate_url',valid)
 with TestClient(app.app) as c:
  login=c.post('/api/login',json={'password':'unit-testing-password'},headers={'Origin':'http://testserver'})
  c.headers.update({'Origin':'http://testserver','X-CSRF-Token':login.json()['csrf']})
  yield c,app.engine

def test_api_profiles_masking_and_busy_guard(client,monkeypatch):
 c,e=client
 data={'provider':'openrouter','model':'test-model','api_key':'private-test-value','vision':False}
 assert c.put('/api/model/settings',json=data).status_code==200
 assert 'private-test-value' not in c.get('/api/model/settings').text
 assert c.get('/api/session').json()['model']=='test-model'
 monkeypatch.setattr(e,'job',SimpleNamespace(done=lambda:False))
 assert c.put('/api/model/settings',json=data).status_code==409
 assert c.delete('/api/model/settings/openrouter').status_code==409
 monkeypatch.setattr(e,'job',None)
 assert c.delete('/api/model/settings/openrouter').status_code==200

def test_draft_probe_uses_structured_output_and_does_not_save(client,monkeypatch):
 c,e=client
 class Model:
  async def ainvoke(self,messages,output_format):
   assert isinstance(messages[0].content,list)
   import base64,io
   from PIL import Image
   part=messages[0].content[1]
   Image.open(io.BytesIO(base64.b64decode(part.image_url.url.split(',')[1]))).verify()
   return SimpleNamespace(completion=output_format(ok=True,action='inspect_page',observed_color='blue'))
 monkeypatch.setattr(e,'llm',lambda config:Model())
 result=c.post('/api/model/test',json={'provider':'nvidia','model':'vision-model','api_key':'probe-only','vision':True})
 assert result.status_code==200,result.text
 assert result.json()['vision_tested']
 assert 'nvidia' not in e.models.data()['profiles']

def test_validation_does_not_echo_credentials(client):
 c,_=client
 secret='sensitive-fixture-'+'x'*2050
 response=c.put('/api/model/settings',json={'provider':'nvidia','model':'m','api_key':secret})
 assert response.status_code==422
 assert 'sensitive-fixture' not in response.text

def test_zai_api_defaults_to_text_mode(client):
 c,e=client
 response=c.put('/api/model/settings',json={'provider':'zai','model':'glm-4.5-flash','api_key':'fixture.id-secret'})
 assert response.status_code==200,response.text
 assert response.json()['profiles']['zai']['vision'] is False
 assert e.models.active()['base_url']=='https://api.z.ai/api/paas/v4'
 assert c.get('/api/session').json()['provider']=='zai'

def test_model_success_reports_missing_browser_separately(client,monkeypatch):
 c,e=client
 class Model:
  async def ainvoke(self,messages,output_format):return SimpleNamespace(completion=output_format(ok=True,action='inspect_page',observed_color='blue'))
 async def absent():return {'installed':False,'code':'BROWSER_MISSING','message':'install chromium'},'/missing'
 monkeypatch.setattr(e,'llm',lambda config:Model())
 monkeypatch.setattr('app.browser_runtime',absent)
 r=c.post('/api/model/test',json={'provider':'zai','model':'glm-4.5-flash','api_key':'fixture-only','vision':False})
 assert r.status_code==200 and r.json()['ok'] is True
 assert r.json()['browser']['code']=='BROWSER_MISSING'

def test_proxy_failure_is_not_reported_as_bad_model_key(client,monkeypatch):
 c,e=client
 monkeypatch.setattr(e,'proxy_config',{'enabled':True,'scope':'application'})
 class Model:
  async def ainvoke(self,*args,**kwargs):
   e.proxy.last_error={'code':'PROXY_AUTH_FAILED','message':'proxy rejected authentication'}
   raise ConnectionError('private detail')
 monkeypatch.setattr(e,'llm',lambda config:Model())
 r=c.post('/api/model/test',json={'provider':'zai','model':'glm-4.5-flash','api_key':'fixture','vision':False})
 assert r.status_code==502 and 'PROXY_AUTH_FAILED' in r.json()['detail']
 assert 'private detail' not in r.text

def test_limits_api_and_saved_task_usage(client,monkeypatch,tmp_path):
 c,e=client
 import app
 storage=Store(tmp_path/'limits')
 monkeypatch.setattr(app,'store',storage);monkeypatch.setattr(e,'store',storage)
 monkeypatch.setattr(e,'task',{'id':'fixture-usage','status':'paused'})
 assert c.put('/api/task/settings',json={'token_limit':0}).status_code==422
 assert c.put('/api/task/settings',json={'cost_limit_usd':1}).status_code==422
 assert c.put('/api/task/settings',json={'token_limit':500}).status_code==200
 assert e.task['limits']['token_limit']==500
 assert c.get('/api/tasks/fixture-usage/usage').json()['calls']==0
 assert c.get('/api/tasks/missing-task/usage').status_code==404
 monkeypatch.setattr(e,'job',SimpleNamespace(done=lambda:False))
 assert c.put('/api/task/settings',json={}).status_code==409
 monkeypatch.setattr(e,'job',None)

def test_probe_rejects_acceptance_without_visual_recognition(client,monkeypatch):
 c,e=client
 class Model:
  async def ainvoke(self,messages,output_format):return SimpleNamespace(completion=output_format(ok=True,action='inspect_page',observed_color='red'))
 monkeypatch.setattr(e,'llm',lambda config:Model())
 r=c.post('/api/model/test',json={'provider':'zai','model':'m','api_key':'fixture','vision':True})
 assert r.status_code==502
 assert 'MODEL_VISION_FAILED' in r.json()['detail']

@pytest.mark.parametrize('status,code',[(400,'MODEL_BAD_REQUEST'),(401,'MODEL_AUTH'),(402,'MODEL_PAYMENT_REQUIRED'),(403,'MODEL_FORBIDDEN'),(404,'MODEL_NOT_FOUND'),(429,'MODEL_RATE_LIMIT'),(503,'MODEL_PROVIDER_ERROR')])
def test_model_failure_has_safe_actionable_diagnostic(client,monkeypatch,status,code):
 c,e=client
 class ProviderError(Exception):
  status_code=status
 class Model:
  async def ainvoke(self,*args,**kwargs):raise ProviderError('private-server-details')
 monkeypatch.setattr(e,'llm',lambda config:Model())
 r=c.post('/api/model/test',json={'provider':'custom','model':'m','api_key':'private-fixture','base_url':'https://example.com/v1','vision':False})
 assert r.status_code==502 and code in r.json()['detail']
 assert 'private-server-details' not in r.text and 'private-fixture' not in r.text
