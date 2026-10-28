"""Check a disposable normal production container and drain an open authenticated SSE on SIGTERM."""
import asyncio,json,os,subprocess,time,argparse
from pathlib import Path
import httpx
async def main(args):
 report={};client=httpx.AsyncClient(base_url=args.url,trust_env=False,timeout=15)
 stream_open=asyncio.Event();stream_task=None
 async def stream():
  async with client.stream('GET','/api/events') as response:
   response.raise_for_status()
   async for line in response.aiter_lines():
    if line.startswith('data: '):stream_open.set()
  report['sse_drained']=True
 try:
  for _ in range(30):
   try:
    r=await client.get('/readyz');r.raise_for_status();break
   except httpx.HTTPError:await asyncio.sleep(1)
  r=await client.post('/api/login',json={'password':os.getenv('TEST_APP_PASSWORD','container-testing-password')},headers={'Origin':args.url});r.raise_for_status()
  headers={'Origin':args.url,'X-CSRF-Token':r.json()['csrf']}
  assert (await client.get('/__qa/metrics')).status_code==404
  assert (await client.get('/__test/archive')).status_code==404
  r=await client.post('/api/browser/open',json={'url':'https://example.com'},headers=headers);r.raise_for_status()
  runtime=(await client.get('/api/runtime')).json();assert runtime['browser']['installed']
  report.update(normal_entrypoint_ready=True,qa_routes_absent=True,real_browser_open=True,memory_limit_bytes=runtime['service']['memory_limit_bytes'])
  assert report['memory_limit_bytes']==2*1024**3
  stream_task=asyncio.create_task(stream());await asyncio.wait_for(stream_open.wait(),10)
  started=time.monotonic()
  await asyncio.to_thread(subprocess.run,['docker','stop','--timeout','45',args.container],check=True,capture_output=True)
  report['shutdown_seconds']=round(time.monotonic()-started,2)
  await asyncio.wait_for(stream_task,10)
  state=json.loads(subprocess.check_output(['docker','inspect',args.container],text=True))[0]
  report['exit_code']=state['State']['ExitCode'];report['oom_killed']=state['State']['OOMKilled']
  logs=subprocess.check_output(['docker','logs',args.container],text=True,stderr=subprocess.STDOUT)
  report['shutdown_log_complete']='Application shutdown complete' in logs
  assert not report['oom_killed'] and report['shutdown_log_complete'] and report['shutdown_seconds']<30
  report['status']='passed'
 finally:
  if stream_task and not stream_task.done():stream_task.cancel();await asyncio.gather(stream_task,return_exceptions=True)
  await client.aclose();Path(args.output).write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8767');parser.add_argument('--container',required=True);parser.add_argument('--output',default='/tmp/dot-production-report.json');asyncio.run(main(parser.parse_args()))
