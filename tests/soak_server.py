"""QA only: deterministic long-running model and fault controls; excluded from Docker production."""
import asyncio,os,sys,time,uuid
os.environ.setdefault('BROWSER_UPSTREAM_PROXY',os.getenv('HTTPS_PROXY',''))
sys.path.insert(0,'/app' if os.path.exists('/app/app.py') else str(__import__('pathlib').Path(__file__).resolve().parents[1]))
import app,uvicorn
from fastapi import Depends
from browser_use.llm.views import ChatInvokeCompletion
from usage import normalized_usage
control={'finish':False,'fault':False};boot=uuid.uuid4().hex
class Model:
 model='soak-scripted';name=model;model_name=model;provider='test';_verified_api_keys=True
 async def ainvoke(self,messages,output_format=None,**kwargs):
  await asyncio.sleep(float(os.getenv('QA_MODEL_DELAY','4')))
  if control['fault']:
   control['fault']=False
   import httpx
   raise httpx.ReadTimeout('Controlled QA provider timeout')
  if output_format is None:return ChatInvokeCompletion(completion='QA history: read page, continue reading until controller requests finish.',usage=normalized_usage({'input_tokens':100,'output_tokens':20}))
  action={'done':{'text':'Controlled endurance task completed','success':True}} if control['finish'] else {'find_elements':{'selector':'a','attributes':['href'],'max_results':3}}
  payload={'evaluation_previous_goal':'Current page observed','memory':'Controlled QA, no real model intelligence','next_goal':'Read the current page until the QA controller finishes','action':[action]}
  return ChatInvokeCompletion(completion=output_format.model_validate(payload),usage=normalized_usage({'input_tokens':100,'output_tokens':20}))
app.engine.llm=lambda:Model()
@app.app.post('/__qa/seed',dependencies=[Depends(app.owner)])
async def seed():
 await app.engine.layout(2200)
 offline=os.getenv('QA_OFFLINE_FIXTURE')=='1'
 if offline:
  await app.engine.ensure_browser()
  if await app.engine.browser.get_current_page() is None:await app.engine.browser.new_page()
  await app.engine.ensure_metrics()
 else:await app.engine.navigate('https://example.com')
 session=await app.engine.browser.get_or_create_cdp_session()
 await session.cdp_client.send.Runtime.evaluate(params={'expression':"document.body.innerHTML='<h1>Controlled endurance fixture — no real AI inference</h1><p id=clock></p>'+Array.from({length:150},(_,i)=>'<p>Controlled website content '+i+' <a href=https://example.com>Example</a></p>').join('');setInterval(()=>document.getElementById('clock').textContent=new Date().toISOString(),1000)"},session_id=session.session_id)
 return {'ok':True,'offline':offline}
@app.app.post('/__qa/fault',dependencies=[Depends(app.owner)])
async def fault():control['fault']=True;return {'ok':True}
@app.app.post('/__qa/finish',dependencies=[Depends(app.owner)])
async def finish():control['finish']=True;return {'ok':True}
@app.app.get('/__qa/metrics',dependencies=[Depends(app.owner)])
async def metrics():
 import psutil
 process=psutil.Process();agent=app.engine.agent
 diagnostics={'python_rss_bytes':process.memory_info().rss,'python_fds':process.num_fds(),'child_processes':len(process.children(recursive=True)),'agent_history_items':len(agent.history.history) if agent else 0}
 return {'boot':boot,'runtime':app.engine.runtime.public(),'status':app.engine.task.get('status') if app.engine.task else None,'steps':app.engine.task.get('steps',0) if app.engine.task else 0,'diagnostics':diagnostics}
if __name__=='__main__':
 from serve import run
 run(app.app,app.engine)
