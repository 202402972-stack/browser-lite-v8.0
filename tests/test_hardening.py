import asyncio,tempfile,json
import pytest
from network import parse_proxy,PublicProxy,ProxyError
from providers import RoutedModel
from engine import Engine,SafeTools
from store import Store
from browser_use import Tools
from browser_use.agent.views import ActionResult

def test_webshare_paste_formats():
 p=parse_proxy('192.0.2.1:6014:fixture-user:fixture:password')
 assert p['scheme']=='http' and p['port']==6014 and p['password']=='fixture:password'
 assert parse_proxy('192.0.2.1:6014')['host']=='192.0.2.1'
 assert parse_proxy('socks5://name:p%40ss@host:8080')['password']=='p@ss'

def test_proxy_auth_error_has_distinct_code():
 async def run():
  async def reject(r,w):
   await r.readuntil(b'\r\n\r\n');w.write(b'HTTP/1.1 407 Proxy Authentication Required\r\n\r\n');await w.drain();w.close()
  server=await asyncio.start_server(reject,'127.0.0.1',0);p=PublicProxy();p.upstream=parse_proxy(f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}');port=await p.start()
  try:
   r,w=await asyncio.open_connection('127.0.0.1',port);w.write(b'CONNECT example.com:443 HTTP/1.1\r\n\r\n');await w.drain();assert b'502' in await r.readuntil(b'\r\n\r\n')
   assert p.last_error['code']=='PROXY_AUTH_FAILED';w.close()
  finally:await p.close();server.close();await server.wait_closed()
 asyncio.run(run())

def test_model_requests_use_gateway_and_fail_closed(monkeypatch):
 import httpx
 async def run():
  with tempfile.TemporaryDirectory() as d:
   e=Engine(Store(d));await e.configure_proxy(True,'http://broken.proxy:8000',scope='application');seen=[]
   async def fail(config,host,port):seen.append((host,port));raise ProxyError('PROXY_AUTH_FAILED','fixture rejection')
   e.proxy.tunnel=fail
   class Model:
    def __init__(self,client):self.client=client
    async def ainvoke(self,*a,**kw):return await self.client.get('https://example.com/')
   m=RoutedModel({'provider':'fixture','model':'test'},e.model_proxy_url,lambda client,proxy:Model(client),lambda text:None)
   try:
    with pytest.raises(httpx.ProxyError):await m.ainvoke([])
    assert seen==[('example.com',443)]
    assert e.proxy.last_error['code']=='PROXY_AUTH_FAILED'
   finally:await e.close()
 asyncio.run(run())

def test_stale_tool_result_requests_fresh_page(monkeypatch):
 async def run():
  with tempfile.TemporaryDirectory() as d:
   e=Engine(Store(d));e.task={'id':'stale','allow_actions':True,'status':'running'};tools=SafeTools(e);Action=tools.registry.create_action_model()
   async def stale(*args,**kwargs):return ActionResult(extracted_content='Element index 1 not available - page may have changed. Try refreshing browser state.')
   monkeypatch.setattr(Tools,'act',stale)
   result=await tools.act(Action(click={'index':1}),None)
   assert result.error and e.task['events'][-1]['kind']=='error'
 asyncio.run(run())

def test_disconnected_browser_is_reopened(monkeypatch):
 import engine as module
 async def run():
  with tempfile.TemporaryDirectory() as d:
   e=Engine(Store(d));closed=[]
   class Dead:
    is_cdp_connected=False
    async def kill(self):closed.append(True)
   class Fresh:
    def __init__(self,**kw):pass
    async def start(self):pass
    async def kill(self):pass
   e.browser=Dead();e.proxy_port=9000
   async def metrics():pass
   e.ensure_metrics=metrics
   monkeypatch.setattr(module,'Browser',Fresh)
   await e.ensure_browser();assert closed and isinstance(e.browser,Fresh)
   await e.close_browser()
 asyncio.run(run())

def test_google_receives_managed_egress_client(monkeypatch):
 import engine as module
 clients=[]
 class Google:
  def __init__(self,**kw):clients.append(kw['http_options']['httpx_async_client'])
  async def ainvoke(self,*args,**kwargs):return 'fixture response'
 monkeypatch.setattr(module,'ChatGoogle',Google)
 async def run():
  with tempfile.TemporaryDirectory() as d:
   e=Engine(Store(d));await e.configure_proxy(True,'http://broken.proxy:8000',scope='application')
   m=e.llm({'provider':'google','model':'fixture','api_key':'fixture-key','base_url':'','vision':False})
   try:
    assert await m.ainvoke([])=='fixture response'
    assert e.proxy_port is not None and clients[0].is_closed
   finally:await e.close()
 asyncio.run(run())
