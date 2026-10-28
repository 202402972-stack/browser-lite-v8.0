"""One active model profile; credentials stay encrypted on the server."""
import os,time
from urllib.parse import urlsplit
PRESETS={
 'agent_router':{'base_url':'https://agentrouter.org/v1','model':'gpt-6.1-sol'},
 'openrouter':{'base_url':'https://openrouter.ai/api/v1','model':'openrouter/free'},
 'google':{'base_url':'','model':'gemini-2.5-flash'},
 'nvidia':{'base_url':'https://integrate.api.nvidia.com/v1','model':''},
 'zai':{'base_url':'https://api.z.ai/api/paas/v4','model':'glm-4.6v-flash','vision':True},
 'custom':{'base_url':'','model':''},
}
def default_vision(provider,model):
 if provider=='zai' and model.lower().startswith('glm-4.5'):return False
 return PRESETS.get(provider,{}).get('vision',True)

class ModelSettings:
 def __init__(self,store):self.store=store
 def data(self):return self.store.secret('models') or {'active':None,'profiles':{}}
 def environment(self):
  provider=os.getenv('LLM_PROVIDER','agent_router');preset=PRESETS.get(provider,{});model=os.getenv('LLM_MODEL') or preset.get('model','')
  return {'provider':provider,'base_url':os.getenv('LLM_BASE_URL') or preset.get('base_url',''),'model':model,'api_key':os.getenv('LLM_API_KEY',''),'vision':os.getenv('USE_VISION','true' if default_vision(provider,model) else 'false').lower()=='true','transport':os.getenv('AGENT_ROUTER_TRANSPORT','codex')}
 def active(self):
  data=self.data();name=data.get('active')
  return dict(data['profiles'][name],provider=name) if name in data['profiles'] else self.environment()
 def public(self):
  data=self.data();active=self.active();profiles={}
  for name,preset in PRESETS.items():
   p=data['profiles'].get(name) or (active if name==active['provider'] else preset)
   profiles[name]={k:p.get(k,default) for k,default in [('base_url',''),('model',''),('vision',preset.get('vision',True))]}
   profiles[name]['has_key']=bool(p.get('api_key'))
   profiles[name]['pricing']=p.get('pricing')
   profiles[name]['context_window']=p.get('context_window',32768)
  return {'active':active['provider'],'source':'saved' if data.get('active') else 'environment','profiles':profiles}
 def resolve(self,body):
  name=body['provider'];preset=PRESETS[name];old=self.data()['profiles'].get(name)
  if not old and self.environment()['provider']==name:old=self.environment()
  old=old or {}
  key=body.get('api_key') or old.get('api_key','')
  base=(body.get('base_url') or preset['base_url']).rstrip('/')
  parsed=urlsplit(base)
  if name!='google' and (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment):raise ValueError('استخدم عنوان HTTPS صالحًا بدون بيانات دخول')
  model=body.get('model','').strip()
  if not model:raise ValueError('اكتب اسم الموديل')
  if not key:raise ValueError('أدخل مفتاح المزوّد')
  pricing=body.get('pricing')
  if pricing:pricing=dict(pricing,checked_at=pricing.get('checked_at') or time.strftime('%Y-%m-%d',time.gmtime()))
  return {'provider':name,'api_key':key,'base_url':base,'model':model,'vision':default_vision(name,model) if body.get('vision') is None else body['vision'],'transport':'codex' if name=='agent_router' else 'chat_completions','pricing':pricing,'context_window':body.get('context_window',32768)}
 def save(self,profile):
  data=self.data();name=profile['provider'];data['profiles'][name]={k:v for k,v in profile.items() if k!='provider'};data['active']=name;self.store.save_secret('models',data)
 def delete(self,name):
  data=self.data();data['profiles'].pop(name,None)
  if data.get('active')==name:data['active']=None
  self.store.save_secret('models',data)
