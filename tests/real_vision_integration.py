"""Optional real-model QA test, NOT a production CAPTCHA benchmark.
Reads a private key interactively; does not save the key.
Run: python tests/real_vision_integration.py
"""
import asyncio,getpass,tempfile,sys,os,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=Path(os.getenv('TEST_OUTPUT_DIR','/tmp/dot-visual-test'));OUT.mkdir(parents=True,exist_ok=True)
key=getpass.getpass('Z.ai key: ')
os.environ['CHROMIUM_SANDBOX']='false';os.environ['BROWSER_UPSTREAM_PROXY']=os.getenv('HTTPS_PROXY','')
async def main():
 from engine import Engine
 from store import Store
 with tempfile.TemporaryDirectory(prefix='dot-real-vision-') as d:
  e=Engine(Store(d));e.models.active=lambda:{'provider':'zai','model':'glm-4.6v-flash','api_key':key,'base_url':'https://api.z.ai/api/paas/v4','vision':True}
  try:
   await e.navigate('https://example.com');session=await e.browser.get_or_create_cdp_session()
   html='''<html><head><meta charset="utf-8"><style>body{font:24px system-ui;margin:50px;background:#e8e2d4;color:#24211e}button{width:120px;height:120px;border:3px solid white;border-radius:14px;margin:10px;font:24px system-ui}.g-recaptcha{padding:24px;border:1px solid #aaa;border-radius:20px;width:700px}</style></head><body><h1>Local visual UI test — NOT a real CAPTCHA</h1><p>Select the blue square. The website will show Accepted.</p><div class="g-recaptcha"><button data-choice="0" style="background:#d67d38">1</button><button data-choice="1" style="background:#2699e6">2</button><button data-choice="2" style="background:#a176cf">3</button><button data-choice="3" style="background:#83b65c">4</button><textarea name="g-recaptcha-response" style="display:none"></textarea><p id="result">Waiting for a choice</p></div></body></html>'''
   expr='document.open();document.write('+json.dumps(html)+');document.close();window.testAttempts=0;document.querySelectorAll("[data-choice]").forEach(b=>b.onclick=()=>{window.testAttempts++;if(b.dataset.choice==="1"){document.querySelector("[name=g-recaptcha-response]").value="local-test-response";document.getElementById("result").textContent="Accepted — local visual test passed"}else document.getElementById("result").textContent="Wrong choice — try again"})'
   await session.cdp_client.send.Runtime.evaluate(params={'expression':expr},session_id=session.session_id)
   start=time.monotonic();await e.start('','هذه صفحة اختبار واجهة محلية وليست CAPTCHA حقيقيًا. من الصورة اختر المربع الأزرق، ثم اقرأ نتيجة الاختبار أسفله وانتهِ باستخدام done عندما يظهر Accepted. لا تستخدم extract؛ النتيجة ظاهرة في الصفحة.')
   try:await asyncio.wait_for(asyncio.shield(e.job),160)
   except TimeoutError:await e.pause()
   observed=await session.cdp_client.send.Runtime.evaluate(params={'expression':'JSON.stringify({result:document.getElementById("result").textContent,attempts:window.testAttempts})','returnByValue':True},session_id=session.session_id)
   report={'model':'glm-4.6v-flash','status':e.task['status'],'steps':e.task['steps'],'seconds':round(time.monotonic()-start,1),'message':e.task.get('message'),'observed':json.loads(observed['result']['value']),'events':e.task['events'],'production_captcha_solve_tested':False}
   (OUT/'real-visual-task-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False).replace(key,'[redacted]'),flush=True)
   (OUT/'preview-real-vision-task.png').write_bytes(await e.snapshot())
  finally:await e.close()
asyncio.run(main())
