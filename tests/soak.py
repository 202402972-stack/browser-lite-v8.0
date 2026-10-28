"""HTTP/SSE/two-viewer soak with deterministic model, one provider fault and optional Docker restart.
Run the QA-only server first; never point this at a production-only server.
Default duration 7200s. QA passwords are read from TEST_APP_PASSWORD, never embedded in reports.
"""
import argparse,asyncio,json,os,time,subprocess
from pathlib import Path
import httpx,websockets
def check_liveness(workers,frame_times,event_time,progress_time,now,started,grace_until=0):
 if any(task.done() for task in workers):raise RuntimeError('STREAM_WORKER_STOPPED')
 if now-started<60 or now<grace_until:return
 if any(stamp is None or now-stamp>60 for stamp in frame_times):raise RuntimeError('FRAME_STREAM_STALLED')
 if event_time is None or now-event_time>60:raise RuntimeError('SSE_STREAM_STALLED')
 if now-progress_time>90:raise RuntimeError('TASK_PROGRESS_STALLED')

async def wait_until_running(get):
 for _ in range(120):
  state=await get('/api/state')
  if state['task']['status']=='running':return
  if state['task']['status']!='starting':raise RuntimeError('Task did not enter running state')
  await asyncio.sleep(.5)
 raise RuntimeError('Timed out waiting for running state')

async def main(args):
 started=time.monotonic();cookie='';headers={};last_id='';stop=False
 frame_times=[None,None];event_time=None;progress_time=started;previous_steps=0;grace_until=0
 report={'requested_seconds':args.duration,'started_at':time.time(),'deterministic_inference':True,'samples':[],'frames':[0,0],'sse_snapshots':0,'restart_verified':False,'injected_provider_fault':False}
 client=httpx.AsyncClient(base_url=args.url,trust_env=False,timeout=15)
 async def login():
  nonlocal cookie,headers
  for _ in range(45):
   try:
    r=await client.post('/api/login',json={'password':os.getenv('TEST_APP_PASSWORD','container-testing-password')},headers={'Origin':args.url});r.raise_for_status()
    headers={'Origin':args.url,'X-CSRF-Token':r.json()['csrf']};cookie='; '.join(k+'='+v for k,v in client.cookies.items())
    return
   except httpx.HTTPError:await asyncio.sleep(1)
  raise RuntimeError('QA server unavailable')
 async def post(path,body=None):
  # Browser launch and the seed navigation have their own longer timeouts.
  r=await client.post(path,json=body or {},headers=headers,timeout=70 if path=='/__qa/seed' else 15);r.raise_for_status();return r.json()
 async def get(path):
  r=await client.get(path);r.raise_for_status();return r.json()
 async def viewer(index):
  while not stop:
   try:
    # The viewer connects to the QA service on the local test network, not
    # through any inherited external HTTP proxy.
    async with websockets.connect(args.url.replace('http','ws',1)+'/api/browser/live',origin=args.url,additional_headers={'Cookie':cookie},max_size=4*1024**2,proxy=None) as ws:
     until=time.monotonic()+45+index*10
     async for message in ws:
      if isinstance(message,bytes):
       assert message.startswith(b'\xff\xd8');report['frames'][index]+=1;frame_times[index]=time.monotonic()
      if time.monotonic()>until:break
   except (OSError,websockets.WebSocketException):pass
   await asyncio.sleep(.5)
 async def timeline():
  nonlocal last_id,event_time
  while not stop:
   try:
    async with httpx.AsyncClient(trust_env=False,timeout=httpx.Timeout(10,read=None)) as stream:
     async with stream.stream('GET',args.url+'/api/events',headers={'Cookie':cookie,'Last-Event-ID':last_id}) as response:
      response.raise_for_status();until=time.monotonic()+60
      async for line in response.aiter_lines():
       if line.startswith('id: '):last_id=line[4:]
       if line.startswith('data: '):json.loads(line[6:]);report['sse_snapshots']+=1;event_time=time.monotonic()
       if time.monotonic()>until:break
   except (httpx.HTTPError,ValueError):pass
   await asyncio.sleep(.5)
 workers=[]
 try:
  await login();seed=await post('/__qa/seed');report['offline_fixture']=bool(seed.get('offline'))
  await post('/api/tasks',{'instruction':'Controlled endurance fixture: read page links and continue until QA finishes.'})
  task_id=(await get('/api/state'))['task']['id']
  # Measure the requested duration from the running state, not server setup.
  await wait_until_running(get)
  task_started=time.monotonic();progress_time=task_started
  report['setup_seconds']=round(task_started-started,1)
  workers=[asyncio.create_task(viewer(0)),asyncio.create_task(viewer(1)),asyncio.create_task(timeline())]
  next_sample=time.monotonic();restarted=False
  while time.monotonic()-task_started<args.duration:
   elapsed=time.monotonic()-task_started
   if not report['injected_provider_fault'] and elapsed>=args.duration*.25:
    await post('/__qa/fault');report['injected_provider_fault']=True
   if args.container and not restarted and elapsed>=args.duration*.5:
    before=(await get('/api/state'))['task'];report['steps_before_restart']=before['steps']
    restart_started=time.monotonic()
    await asyncio.to_thread(subprocess.run,['docker','restart','--timeout','45',args.container],check=True,capture_output=True)
    report['restart_elapsed_seconds']=round(time.monotonic()-restart_started,2)
    await login();after=(await get('/api/state'))['task']
    assert after['id']==task_id and after['steps']>=before['steps'] and after['status']=='paused',after
    if report['offline_fixture']:await post('/__qa/seed')
    await post('/api/control/resume');report['restart_verified']=True;restarted=True
    grace_until=time.monotonic()+45;progress_time=time.monotonic()
   if time.monotonic()>=next_sample:
    ready=await get('/readyz');assert ready['ready']
    metrics=await get('/__qa/metrics');report['samples'].append(dict(metrics,elapsed=round(elapsed,1)))
    if metrics['steps']!=previous_steps:progress_time=time.monotonic();previous_steps=metrics['steps']
    check_liveness(workers,frame_times,event_time,progress_time,time.monotonic(),task_started,grace_until)
    Path(args.output).write_text(json.dumps(dict(report,status='running',elapsed_seconds=round(time.monotonic()-started,1),task_elapsed_seconds=round(time.monotonic()-task_started,1)),indent=2))
    if metrics['status'] not in ('starting','running'):raise AssertionError('Task stopped unexpectedly: '+str(metrics['status']))
    print(json.dumps({'elapsed':round(elapsed,1),'steps':metrics['steps'],'working_set_mib':round((metrics['runtime']['working_set_bytes'] or 0)/1024**2,1),'frames':report['frames']}),flush=True)
    next_sample=time.monotonic()+15
   await asyncio.sleep(1)
  report['task_elapsed_seconds']=round(time.monotonic()-task_started,1)
  await post('/__qa/finish')
  for _ in range(60):
   state=await get('/api/state')
   if not state['busy']:break
   await asyncio.sleep(1)
  assert state['task']['status']=='completed',state['task'].get('diagnostic')
  count=0;after=0
  while True:
   page=await get('/api/tasks/'+task_id+'/events?after='+str(after)+'&limit=500')
   for event in page['events']:
    assert event['seq']==after+1,'ARCHIVE_SEQUENCE_GAP';after=event['seq'];count+=1
   if not page['has_more']:break
  check_liveness(workers,frame_times,event_time,progress_time,time.monotonic(),task_started,grace_until)
  assert min(report['frames'])>0 and report['sse_snapshots']>0
  assert state['usage']['unknown_calls']>=1
  report.update(status='passed',task_id=task_id,steps=state['task']['steps'],archive_events=count,reported_tokens=state['usage']['total_tokens'],unknown_calls=state['usage']['unknown_calls'],peak_sampled_mib=round(max(s['runtime']['working_set_bytes'] or 0 for s in report['samples'])/1024**2,1))
 except BaseException as exc:
  report.update(status='failed',error_type=type(exc).__name__)
  raise
 finally:
  stop=True
  for task in workers:task.cancel()
  await asyncio.gather(*workers,return_exceptions=True);await client.aclose()
  report['elapsed_seconds']=round(time.monotonic()-started,1);Path(args.output).write_text(json.dumps(report,indent=2))
  print(json.dumps({k:v for k,v in report.items() if k!='samples'}),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8767');parser.add_argument('--container');parser.add_argument('--duration',type=int,default=7200);parser.add_argument('--output',default='/tmp/dot-soak-report.json');args=parser.parse_args()
 if args.duration<60:parser.error('duration must be at least 60 seconds')
 asyncio.run(main(args))
