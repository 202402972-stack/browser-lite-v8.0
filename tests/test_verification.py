import asyncio,tempfile,time
from engine import Engine
from store import Store

def fixture_engine(path,vision=False):
 e=Engine(Store(path));e.task={'id':'verification-test','status':'running','allow_actions':True}
 e.models.active=lambda:{'vision':vision}
 e.browser=object()
 async def session():return object()
 e.browser=type('Browser',(),{'get_or_create_cdp_session':lambda self:session()})()
 return e

def test_checkbox_is_attempted_once_and_no_false_success(tmp_path):
 async def run():
  e=fixture_engine(tmp_path);v=e.verification;sent=[]
  class Input:
   async def dispatchMouseEvent(self,**kw):sent.append(kw)
  root=type('Session',(),{'session_id':'root','cdp_client':type('Client',(),{'send':type('Send',(),{'Input':Input()})()})()})()
  async def session():return root
  e.browser.get_or_create_cdp_session=session
  async def evaluate(*args,**kw):return {'present':True,'vendor':'recaptcha','url':'https://example.com','tokens':False}
  async def boxes(*args):return [({'x':30,'y':30,'width':300,'height':100,'checked':False},None)]
  v.evaluate=evaluate;v.candidates=boxes
  await v.scan();assert len(sent)==2 and v.active
  v.clicked_at=time.monotonic()-10
  await v.scan();await v.scan()
  assert len(sent)==2 and e.task['verification']['state']=='needs_user'
  assert not any(x['title'].startswith('اكتمل مؤشر') for x in e.task['events'])
  count=len(e.task['events']);await v.scan();assert len(e.task['events'])==count
 asyncio.run(run())

def test_visual_model_can_work_with_bounded_attempts(tmp_path):
 async def run():
  e=fixture_engine(tmp_path,True);v=e.verification
  async def evaluate(*args,**kw):return {'present':True,'vendor':'recaptcha','url':'https://example.com','tokens':False}
  async def boxes(*args):return []
  v.evaluate=evaluate;v.candidates=boxes
  await v.scan();assert e.task['verification']['state']=='ai_solving'
  assert await v.guard() is False
  v.ai_actions=12;await v.scan();assert e.task['status']=='waiting_user'
 asyncio.run(run())

def test_oopif_with_empty_target_url_uses_frame_location_once(tmp_path):
 from types import SimpleNamespace
 from verification import CHECKBOX_SCAN
 async def run():
  e=fixture_engine(tmp_path);v=e.verification
  frame={'url':'https://www.google.com/recaptcha/api2/anchor?test=1','x':20,'y':30,'width':300,'height':80}
  session=SimpleNamespace(target_id='frame-1')
  manager=SimpleNamespace(get_all_sessions=lambda:{'a':session,'b':session},get_target=lambda _:SimpleNamespace(target_type='iframe',url=''))
  e.browser.session_manager=manager;root=object()
  async def evaluate(target,expression,context=None):
   if target is root:return None
   if expression=='location.href':return frame['url']
   if expression==CHECKBOX_SCAN:return {'x':20,'y':20,'width':300,'height':80,'checked':False}
  v.evaluate=evaluate
  result=await v.candidates(root,{'frames':[frame]})
  assert len(result)==1 and result[0][1]==frame
 asyncio.run(run())

def test_provider_response_clears_wait_without_exposing_token(tmp_path):
 async def run():
  e=fixture_engine(tmp_path);v=e.verification;v.active=True
  e.task.update(status='waiting_user',pending={'name':'verification'})
  async def evaluate(*args,**kw):return {'present':True,'vendor':'recaptcha','tokens':True}
  async def boxes(*args):return []
  v.evaluate=evaluate;v.candidates=boxes
  await v.scan();assert not v.active and e.task['status']=='running' and e.task['pending'] is None
  assert e.task['verification']['state']=='cleared'
 asyncio.run(run())

def test_upstream_local_defaults_are_retained(tmp_path):
 from browser_use.browser.profile import BrowserProfile
 profile=BrowserProfile(headless=True,user_data_dir=str(tmp_path/'profile'),enable_default_extensions=False,args=['--disable-quic'],captcha_solver=True)
 args=profile.get_args()
 assert any(arg.startswith('--disable-blink-features=') and 'AutomationControlled' in arg for arg in args)
 assert profile.captcha_solver is True

def test_changed_verification_invalidates_prior_action_even_after_clear(tmp_path):
 from engine import SafeTools
 async def run():
  e=fixture_engine(tmp_path,True);v=e.verification
  v.active=False;v.revision=2;v.decision_revision=1
  async def guard():return False
  v.guard=guard
  tools=SafeTools(e);Action=tools.registry.create_action_model()
  result=await tools.act(Action(click={'index':1}),None)
  assert result.error and 'state changed' in result.error
 asyncio.run(run())
