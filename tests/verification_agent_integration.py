"""Scripted vision-model control flow on a local fixture, NOT real CAPTCHA solving."""
import asyncio,tempfile,json,re
from engine import Engine
from store import Store
from browser_use.llm.views import ChatInvokeCompletion
class Model:
 model='vision-fixture';name='vision-fixture';model_name='vision-fixture';provider='test';_verified_api_keys=True
 def __init__(self):self.calls=0
 async def ainvoke(self,messages,output_format=None,**kwargs):
  self.calls+=1
  data=[m.model_dump(mode='json') for m in messages]
  assert any(isinstance(m.get('content'),list) and any(p.get('type')=='image_url' for p in m['content']) for m in data),'Screenshot must reach configured visual model'
  if self.calls==1:
   text='\n'.join(p.get('text','') for m in data if m.get('role')=='user' for p in (m['content'] if isinstance(m['content'],list) else [{'text':m['content']}]))
   match=re.search(r'\[(\d+)\]<button[^\n]*>\s*Complete test verification',text)
   assert match,'Controlled button must be indexed'
   action={'click':{'index':int(match.group(1))}}
  else:action={'done':{'text':'Local visual control-flow test passed','success':True}}
  return ChatInvokeCompletion(completion=output_format.model_validate({'evaluation_previous_goal':'Observed fixture','memory':'Controlled test only','next_goal':'Verify fixture result','action':[action]}),usage=None)
async def main():
 with tempfile.TemporaryDirectory() as d:
  e=Engine(Store(d));model=Model();e.llm=lambda:model;e.models.active=lambda:{'vision':True,'provider':'fixture','model':'fixture'}
  try:
   await e.navigate('https://example.com');session=await e.browser.get_or_create_cdp_session()
   html='<html><body><h1>Local vision-model control-flow fixture, not a CAPTCHA</h1><div class="g-recaptcha" style="width:600px;height:200px"><button style="padding:30px" id="complete">Complete test verification</button><textarea name="g-recaptcha-response" style="display:none"></textarea></div></body></html>'
   expression='document.open();document.write('+json.dumps(html)+');document.close();document.getElementById("complete").onclick=()=>{document.querySelector("[name=g-recaptcha-response]").value="fixture-response";document.getElementById("complete").textContent="Local fixture accepted"}'
   await session.cdp_client.send.Runtime.evaluate(params={'expression':expression},session_id=session.session_id)
   await e.start('','Complete the local verification fixture, then finish.');await asyncio.wait_for(e.job,80)
   assert e.task['status']=='completed',e.task
   assert model.calls==2
   assert any('الإيجنت يفحص التحقق باستخدام الصور' in ev['title'] for ev in e.task['events'])
   assert not any(ev['kind']=='approval' for ev in e.task['events'])
   print(json.dumps({'scripted_visual_model_calls':model.calls,'status':e.task['status'],'real_dom_click':True,'real_captcha_solve_tested':False}))
  finally:await e.close()
asyncio.run(main())
