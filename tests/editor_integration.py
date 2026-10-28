"""Real browser textarea repair and website-side test; no host code execution."""
import asyncio,tempfile,json
from engine import Engine,SafeTools
from store import Store
async def main():
 with tempfile.TemporaryDirectory() as d:
  e=Engine(Store(d));e.task={'id':'coding-fixture','allow_actions':True,'status':'running'}
  try:
   await e.navigate('https://example.com')
   session=await e.browser.get_or_create_cdp_session()
   fixture="""document.body.innerHTML='<textarea id="code" style="position:fixed;left:20px;top:20px;width:500px;height:180px">function add(a,b){return a-b}</textarea><button id="run" style="position:fixed;left:20px;top:230px;width:150px;height:50px">Run tests</button><output id="result"></output>';document.getElementById('run').onclick=()=>{try{const fn=new Function('return ('+document.getElementById('code').value+')')();document.getElementById('result').textContent=fn(2,3)===5?'PASS':'FAIL'}catch(e){document.getElementById('result').textContent='FAIL'}}"""
   await session.cdp_client.send.Runtime.evaluate(params={'expression':fixture},session_id=session.session_id)
   tools=SafeTools(e);Action=tools.registry.create_action_model()
   read=await tools.act(Action(read_editor={'selector':'#code'}),None)
   assert not read.error and 'a-b' in read.extracted_content
   code='function add(a,b){return a+b}'
   written=await tools.act(Action(write_editor={'selector':'#code','code':code}),None)
   assert not written.error,written.error
   await e.input({'kind':'click','x':80,'y':250})
   result=await session.cdp_client.send.Runtime.evaluate(params={'expression':'document.getElementById("result").textContent','returnByValue':True},session_id=session.session_id)
   assert result['result']['value']=='PASS'
   # Ambiguous selectors must not edit an arbitrary second editor.
   await session.cdp_client.send.Runtime.evaluate(params={'expression':'document.body.append(document.createElement("textarea"))'},session_id=session.session_id)
   ambiguous=await tools.act(Action(write_editor={'code':'no guessing'}),None)
   assert ambiguous.error
   assert not any(event['kind']=='approval' for event in e.task['events'])
   print(json.dumps({'real_browser_editor_repair':True,'website_test':'PASS','ambiguous_editor_rejected':True,'host_execution':False}))
  finally:await e.close()
asyncio.run(main())
