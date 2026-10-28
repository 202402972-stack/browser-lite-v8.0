import sqlite3, logging, asyncio, base64, hashlib, hmac, json, os, secrets, shutil, time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
os.environ.setdefault('ANONYMIZED_TELEMETRY','false')
os.environ.setdefault('BROWSER_USE_LOGGING_LEVEL','error')
from fastapi import FastAPI, Request, Response, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal
from store import Store,SecretUnavailable
from engine import Engine
from runtime_checks import browser_runtime,RuntimeDependencyError

ROOT=Path(__file__).parent
store=Store(os.getenv('DATA_DIR',str(ROOT/'data')))
engine=Engine(store)
sessions={}
attempts={}

@asynccontextmanager
async def lifespan(app):
    if len(os.getenv('APP_PASSWORD',''))<12:
        raise RuntimeError('Set APP_PASSWORD to at least 12 characters')
    engine.closing=False
    async def maintenance():
        last_cleanup=0
        while True:
            await asyncio.sleep(5)
            try:await engine.runtime.tick()
            except asyncio.CancelledError:raise
            except Exception as exc:
                engine.runtime.last_error='MAINTENANCE_FAILED'
                logging.getLogger(__name__).warning('maintenance_failed code=%s',type(exc).__name__)
            if time.monotonic()-last_cleanup<30:continue
            last_cleanup=time.monotonic()
            active=engine.job and not engine.job.done()
            if not active and time.monotonic()-engine.last_used>120:await engine.close_browser()
            for key,value in list(sessions.items()):
                if value['expires']<time.time():sessions.pop(key,None)
            for key,value in list(attempts.items()):
                recent=[stamp for stamp in value if time.time()-stamp<300]
                if recent:attempts[key]=recent
                else:attempts.pop(key,None)
            downloads=store.root/'downloads'
            try:
                candidates=[]
                for path in downloads.iterdir() if downloads.exists() else []:
                    try:
                        if path.is_file() and not path.is_symlink():candidates.append((path,path.stat()))
                    except OSError:continue
                total=sum(stat.st_size for _,stat in candidates)
                for path,stat in sorted(candidates,key=lambda item:item[1].st_mtime):
                    if time.time()-stat.st_mtime>86400 or stat.st_size>10*1024**2 or total>50*1024**2:
                        try:path.unlink(missing_ok=True);total-=stat.st_size
                        except OSError:continue
            except OSError:pass
    task=asyncio.create_task(maintenance())
    try:yield
    finally:
        engine.closing=True;task.cancel()
        await asyncio.gather(task,return_exceptions=True)
        await engine.close()

app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
@app.exception_handler(RequestValidationError)
async def invalid_input(request,exc):
    # Validation errors must not echo an API key or password from the request.
    return JSONResponse(status_code=422,content={'detail':'راجع الحقول المطلوبة وطول القيم'})

@app.exception_handler(SecretUnavailable)
async def invalid_secret(request,exc):
    return JSONResponse(status_code=503,content={'code':'SETTINGS_UNAVAILABLE','detail':str(exc)})


def same_origin(request):
    origin=request.headers.get('origin')
    if not origin:return False
    p=urlsplit(origin)
    return p.scheme in ('http','https') and p.netloc==request.headers.get('host')

def authenticate(request):
    token=request.cookies.get('browser_lite_session','')
    entry=sessions.get(hashlib.sha256(token.encode()).hexdigest())
    if not entry or entry['expires']<time.time():raise HTTPException(401,'سجّل الدخول أولًا')
    return entry

async def owner(request:Request):
    entry=authenticate(request)
    if request.method not in ('GET','HEAD'):
        if not same_origin(request) or not hmac.compare_digest(request.headers.get('x-csrf-token',''),entry['csrf']):
            raise HTTPException(403,'Invalid origin or CSRF token')
    return entry

@app.middleware('http')
async def headers(request,call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api') else 'no-cache'
    return response

class Login(BaseModel):password:str=Field(max_length=512)
@app.post('/api/login')
async def login(body:Login,request:Request,response:Response):
    if not same_origin(request):raise HTTPException(403,'Invalid origin')
    ip=request.client.host
    recent=[t for t in attempts.get(ip,[]) if time.time()-t<300]
    if ip not in attempts and len(attempts)>=1000:raise HTTPException(429,'حاول لاحقًا')
    attempts[ip]=recent
    if len(recent)>=10:raise HTTPException(429,'حاول بعد خمس دقائق')
    expected=os.getenv('APP_PASSWORD','')
    if len(expected)<12 or not secrets.compare_digest(body.password,expected):
        recent.append(time.time());raise HTTPException(401,'كلمة المرور غير صحيحة')
    attempts.pop(ip,None)
    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
    # Bound session storage and expire old sessions.
    for k,v in list(sessions.items()):
        if v['expires']<time.time():sessions.pop(k,None)
    if len(sessions)>=100:sessions.clear()
    sessions[hashlib.sha256(token.encode()).hexdigest()]={'csrf':csrf,'expires':time.time()+86400}
    secure=request.url.scheme=='https' or request.headers.get('x-forwarded-proto')=='https'
    response.set_cookie('browser_lite_session',token,httponly=True,secure=secure,samesite='strict',max_age=86400)
    return {'csrf':csrf}

@app.get('/api/session')
async def session(entry=Depends(owner)):
    config=engine.models.active()
    return {'csrf':entry['csrf'],'provider':config['provider'],'model':config['model'],'configured':bool(config['api_key'])}
@app.post('/api/logout')
async def logout(request:Request,response:Response,entry=Depends(owner)):
    sessions.pop(hashlib.sha256(request.cookies.get('browser_lite_session','').encode()).hexdigest(),None)
    response.delete_cookie('browser_lite_session');return {'ok':True}

class TaskLimits(BaseModel):
    token_limit:int|None=Field(default=None,ge=1,le=1_000_000_000)
    cost_limit_usd:float|None=Field(default=None,gt=0,le=100000,allow_inf_nan=False)

class TaskBody(BaseModel):
    url:str=Field(default='',max_length=2048)
    instruction:str=Field(min_length=1,max_length=12000)
    allow_actions:bool=True
    limits:TaskLimits|None=None
class URLBody(BaseModel):url:str=Field(max_length=2048)
class InputBody(BaseModel):
    kind:str
    x:float=0
    y:float=0
    delta:float=0
    text:str=Field(default='',max_length=4000)
    key:str=''

@app.get('/healthz')
def health():return {'ok':True}
@app.get('/readyz')
def ready(response:Response):
    code='SERVICE_STOPPING' if engine.closing else store.last_error
    if code:response.status_code=503
    return {'ready':code is None,'code':code or 'ready'}
@app.get('/api/state',dependencies=[Depends(owner)])
def state():
    task=engine.task;message_history=None
    if task and task.get('id') and not store.last_error:
        try:
            page=store.messages(task['id'],limit=50)
            if page['messages']:task=dict(task,messages=page['messages'])
            message_history={k:page[k] for k in ('has_more','next_before')}
        except sqlite3.Error:store.last_error='STORAGE_READ_FAILED'
    return {'task':task,'message_history':message_history,'usage':engine.usage.public() if engine.task else None,'browser_ready':engine.browser is not None,'busy':bool(engine.job and not engine.job.done()),'files':files(),'viewport':engine.viewport,'proxy':engine.proxy_info()}
@app.get('/api/runtime',dependencies=[Depends(owner)])
async def runtime_status():
    runtime,_=await browser_runtime()
    return {'browser':runtime,'service':engine.runtime.public(),'storage':{'ready':store.last_error is None,'code':store.last_error}}

@app.get('/api/history',dependencies=[Depends(owner)])
def history():return store.history()
@app.post('/api/tasks',dependencies=[Depends(owner)])
async def start(body:TaskBody):
    if not body.instruction.strip():raise HTTPException(422,'اكتب المهمة')
    try:return await engine.start(body.url,body.instruction,body.allow_actions,body.limits.model_dump() if body.limits else None)
    except ValueError as e:raise HTTPException(409 if engine.job and not engine.job.done() else 422,str(e))

@app.get('/api/task/settings',dependencies=[Depends(owner)])
async def task_settings():
    return {'defaults':store.secret('task_limits') or {},'current':engine.task.get('limits',{}) if engine.task else None}

@app.put('/api/task/settings',dependencies=[Depends(owner)])
async def save_task_settings(body:TaskLimits):
    async with engine.lock:
        if engine.job and not engine.job.done():raise HTTPException(409,'أوقف المهمة قبل تغيير السقف')
        if body.cost_limit_usd is not None and not engine.models.active().get('pricing'):
            raise HTTPException(422,'أضف أسعار الموديل قبل استخدام سقف تكلفة')
        limits=body.model_dump();store.save_secret('task_limits',limits)
        if engine.task and engine.task['status'] in ('paused','failed'):engine.update(limits=limits)
        return await task_settings()

@app.get('/api/tasks/{task_id}/usage',dependencies=[Depends(owner)])
async def task_usage(task_id:str):
    from types import SimpleNamespace
    from usage import UsageLedger
    task=engine.task if engine.task and engine.task['id']==task_id else store.get(task_id)
    if not task:raise HTTPException(404,'المهمة غير موجودة')
    return UsageLedger(SimpleNamespace(task=task)).public()
class MessageBody(BaseModel):
    text:str=Field(min_length=1,max_length=12000)
    edit_id:str|None=None
class ProxyBody(BaseModel):
    enabled:bool=False
    scope:Literal['browser','application']='application'
    url:str=Field(default='',max_length=2048)
    username:str=Field(default='',max_length=255)
    password:str=Field(default='',max_length=512)
    keep_password:bool=True
@app.post('/api/messages',dependencies=[Depends(owner)])
async def message(body:MessageBody):
    try:return await engine.message(body.text,body.edit_id)
    except ValueError as e:raise HTTPException(422,str(e))
@app.get('/api/proxy',dependencies=[Depends(owner)])
async def proxy_info():return engine.proxy_info()
@app.put('/api/proxy',dependencies=[Depends(owner)])
async def proxy_config(body:ProxyBody):
    try:return await engine.configure_proxy(**body.model_dump())
    except ValueError as e:raise HTTPException(409 if engine.job and not engine.job.done() else 422,str(e))
@app.post('/api/proxy/test',dependencies=[Depends(owner)])
async def proxy_test():
    import ipaddress
    async with engine.lock:
        if engine.job and not engine.job.done():raise HTTPException(409,'أوقف المهمة قبل فحص البروكسي')
        if not engine.proxy_config.get('enabled'):raise HTTPException(422,'فعّل بروكسي أولًا')
        engine.proxy.last_error=None
        try:
            await asyncio.wait_for(engine.navigate('https://api.ipify.org?format=json'),35)
            session=await engine.browser.get_or_create_cdp_session()
            result=await session.cdp_client.send.Runtime.evaluate(params={'expression':'document.body.innerText','returnByValue':True},session_id=session.session_id)
            text=result.get('result',{}).get('value','')
            ip=str(ipaddress.ip_address(json.loads(text)['ip']))
            engine.proxy_check={'ok':True,'ip':ip,'time':time.time(),'tested':'browser'}
            engine.event('proxy','نجح فحص عنوان الخروج عبر البروكسي')
            return engine.proxy_check
        except Exception:
            engine.proxy_check={'ok':False,'time':time.time(),'diagnostic':engine.proxy.last_error or {'code':'PROXY_TEST_FAILED','message':'فشل فحص الاتصال أو صفحة IP'}}
            diagnostic=engine.proxy_check['diagnostic']
            raise HTTPException(502,diagnostic['code']+': '+diagnostic['message']+'؛ لن يُستخدم اتصال مباشر كبديل.')

@app.post('/api/control/{action}',dependencies=[Depends(owner)])
async def control(action:str):
    try:
        if action=='pause':await engine.pause()
        elif action=='cancel':await engine.pause(cancel=True)
        elif action=='resume':await engine.resume()
        elif action=='approve':await engine.approve()
        else:raise HTTPException(404)
        return {'ok':True}
    except ValueError as e:raise HTTPException(409,str(e))
class BrowserLayout(BaseModel):
    height:int=Field(ge=800,le=2200)
@app.post('/api/browser/layout',dependencies=[Depends(owner)])
async def browser_layout(body:BrowserLayout):
    try:return await engine.layout(body.height)
    except ValueError as e:raise HTTPException(409,str(e))
@app.post('/api/browser/open',dependencies=[Depends(owner)])
async def open_page(body:URLBody):
    async with engine.lock:
        if engine.job and not engine.job.done():raise HTTPException(409,'استلم التحكم أولًا')
        try:
            await engine.navigate(body.url)
            return {'ok':True}
        except ValueError as e:raise HTTPException(422,str(e))
        except RuntimeDependencyError as e:raise HTTPException(503,str(e))
        except Exception as e:raise HTTPException(502,f'تعذر فتح المتصفح ({type(e).__name__})')
@app.post('/api/browser/input',dependencies=[Depends(owner)])
async def browser_input(body:InputBody):
    try:
        await engine.input(body.model_dump());return {'ok':True}
    except ValueError as e:raise HTTPException(409,str(e))
    except TimeoutError:raise HTTPException(503,'المتصفح لم يستجب للإدخال؛ لم تُعد المحاولة تلقائيًا')
@app.post('/api/browser/clear',dependencies=[Depends(owner)])
async def clear():
    if engine.job and not engine.job.done():raise HTTPException(409,'أوقف المهمة أولًا')
    await engine.close_browser()
    shutil.rmtree(store.root/'profile',ignore_errors=True)
    return {'ok':True}

@app.websocket('/api/browser/live')
async def live(ws:WebSocket):
    try:
        if not same_origin(ws):raise ValueError()
        entry=authenticate(ws)
    except Exception:
        await ws.close(code=1008);return
    await ws.accept()
    try:
        while not engine.closing:
            try:authenticate(ws)
            except HTTPException:break
            if engine.browser:
                try:
                    data=await asyncio.wait_for(engine.snapshot(),8)
                    if data is None:await ws.send_json({'status':'closed'});continue
                    url=engine.frame_url or await engine.browser.get_current_page_url()
                    await asyncio.wait_for(ws.send_json({'url':url,'viewport':engine.viewport}),5)
                    if engine.task and url.startswith(('https://','http://')) and engine.task.get('last_url')!=url:
                        engine.update(last_url=url)
                    await asyncio.wait_for(ws.send_bytes(data),5)
                except asyncio.TimeoutError:break
                except WebSocketDisconnect:raise
                except Exception:
                    await ws.send_json({'status':'waiting'})
            else:await ws.send_json({'status':'closed'})
            await asyncio.sleep(1)
    except (WebSocketDisconnect,RuntimeError):pass
    finally:
        try:await ws.close()
        except Exception:pass

def state_cursor(data):
    task=data.get('task') or {}
    return f"{task.get('id','none')}:{task.get('event_seq',max((e['seq'] for e in task.get('events',[])),default=0))}:{task.get('_revision',0)}"

def replay_for(data,cursor):
    try:
        task_id,after,revision=cursor.rsplit(':',2);after=int(after);int(revision)
        task=data.get('task') or {}
        if task_id!=task.get('id') or not 0<=after<2**63:return None
        return store.events(task_id,after=after,limit=500)
    except (ValueError,AttributeError):return None

@app.get('/api/events',dependencies=[Depends(owner)])
async def events(request:Request):
    async def generate():
        old=None;first=True
        while not engine.closing and not await request.is_disconnected():
            try:authenticate(request)
            except HTTPException:break
            snapshot=state();cursor=state_cursor(snapshot)
            if first:
                replay=replay_for(snapshot,request.headers.get('last-event-id') or getattr(request,'query_params',{}).get('cursor',''))
                if replay is not None:snapshot['replay']=replay
                first=False
            data=json.dumps(snapshot,ensure_ascii=False)
            if data!=old:
                yield f'id: {cursor}\ndata: {data}\n\n';old=data
            else:yield ': keepalive\n\n'
            await asyncio.sleep(1)
    return StreamingResponse(generate(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})

@app.get('/api/tasks/{task_id}/events',dependencies=[Depends(owner)])
async def task_events(task_id:str,after:int=Query(0,ge=0,le=2**63-1),before:int|None=Query(None,ge=1,le=2**63-1),limit:int=Query(100,ge=1,le=500)):
    if store.get(task_id) is None:raise HTTPException(404,'المهمة غير موجودة')
    return store.events(task_id,after=after,before=before,limit=limit)

@app.get('/api/tasks/{task_id}/messages',dependencies=[Depends(owner)])
async def task_messages(task_id:str,before:int|None=Query(None,ge=1,le=2**63-1),limit:int=Query(50,ge=1,le=100)):
    if store.get(task_id) is None:raise HTTPException(404,'المهمة غير موجودة')
    return store.messages(task_id,before=before,limit=limit)

def files():
    result=[];directory=store.root/'downloads'
    try:
        for path in directory.iterdir() if directory.exists() else []:
            try:
                if path.is_file() and not path.is_symlink():
                    size=path.stat().st_size
                    if size<=10*1024**2:result.append({'name':path.name,'size':size})
            except OSError:continue
            if len(result)>=30:break
    except OSError:pass
    return result

@app.get('/api/files/{name}',dependencies=[Depends(owner)])
def download(name:str):
    directory=(store.root/'downloads').resolve()
    path=(directory/name).resolve()
    if path.parent!=directory or not path.is_file() or path.stat().st_size>10*1024**2:raise HTTPException(404)
    return FileResponse(path,filename=path.name,media_type='application/octet-stream')

class ModelPricing(BaseModel):
    input:float=Field(ge=0,le=100000,allow_inf_nan=False)
    output:float=Field(ge=0,le=100000,allow_inf_nan=False)
    cached_input:float|None=Field(default=None,ge=0,le=100000,allow_inf_nan=False)
    source:str=Field(default='user',max_length=300)
    checked_at:str=Field(default='',max_length=32)

class ModelBody(BaseModel):
    provider:Literal['agent_router','openrouter','google','nvidia','zai','custom']
    model:str=Field(min_length=1,max_length=200)
    api_key:str=Field(default='',max_length=2048)
    base_url:str=Field(default='',max_length=2048)
    vision:bool|None=None
    pricing:ModelPricing|None=None
    context_window:int=Field(default=32768,ge=8192,le=2_000_000)

async def model_profile(body):
    from network import validate_url
    try:
        profile=engine.models.resolve(body.model_dump())
        if profile['provider']!='google':await validate_url(profile['base_url'],remote_dns=bool(engine.proxy_config.get('enabled') and engine.proxy_config.get('scope')=='application'))
        return profile
    except (ValueError,OSError):raise HTTPException(422,'راجع الموديل والمفتاح وعنوان الخدمة العام HTTPS')

@app.get('/api/model/settings',dependencies=[Depends(owner)])
async def model_settings():return engine.models.public()

@app.put('/api/model/settings',dependencies=[Depends(owner)])
async def save_model(body:ModelBody):
    async with engine.lock:
        if engine.job and not engine.job.done():raise HTTPException(409,'أوقف المهمة قبل تغيير الموديل')
        engine.models.save(await model_profile(body))
        return engine.models.public()

@app.delete('/api/model/settings/{provider}',dependencies=[Depends(owner)])
async def delete_model(provider:Literal['agent_router','openrouter','google','nvidia','zai','custom']):
    async with engine.lock:
        if engine.job and not engine.job.done():raise HTTPException(409,'أوقف المهمة قبل تغيير الموديل')
        engine.models.delete(provider)
        return engine.models.public()

_model_catalog=None
@app.get('/api/model/catalog',dependencies=[Depends(owner)])
async def model_catalog():
    global _model_catalog
    if _model_catalog and time.monotonic()-_model_catalog[0]<300:return _model_catalog[1]
    import httpx
    try:
        proxy=await engine.model_proxy_url()
        async with httpx.AsyncClient(timeout=15,proxy=proxy,trust_env=not bool(proxy)) as client:
            response=await client.get('https://openrouter.ai/api/v1/models');response.raise_for_status()
        models=[{'id':m['id'],'vision':'image' in m.get('architecture',{}).get('input_modalities',[])} for m in response.json()['data'] if float(m.get('pricing',{}).get('prompt',-1))==0 and float(m.get('pricing',{}).get('completion',-1))==0]
        result={'models':models};_model_catalog=(time.monotonic(),result);return result
    except Exception:raise HTTPException(502,'تعذر تحديث القائمة؛ اكتب اسم الموديل يدويًا')

@app.post('/api/model/test',dependencies=[Depends(owner)])
async def model_test(body:ModelBody|None=None):
    from browser_use.llm.messages import UserMessage,ContentPartTextParam,ContentPartImageParam,ImageURL
    from diagnostics import VisionProbeFailed
    from pydantic import BaseModel
    class Probe(BaseModel):
        ok:bool
        action:Literal['inspect_page']
        observed_color:str|None=None
    if engine.job and not engine.job.done():raise HTTPException(409,'أوقف المهمة قبل الاختبار')
    config=await model_profile(body) if body else engine.models.active()
    content='Return ok=true and action=inspect_page. This tests a structured next-action response. If an image is attached, identify its dominant color in English using observed_color; otherwise return null for observed_color.'
    if config['vision']:
        content=[ContentPartTextParam(text=content),ContentPartImageParam(image_url=ImageURL(url='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAKklEQVR4nO3NQQEAAATAQCTUvwwl+N0C7DJ64rN6vQMAAAAAAAAAAIDDFmtiAY8TwohVAAAAAElFTkSuQmCC'))]
    engine.proxy.last_error=None
    try:
        result=await asyncio.wait_for(engine.llm(config).ainvoke([UserMessage(content=content)],output_format=Probe),int(os.getenv('MODEL_TIMEOUT_SECONDS','120'))+5)
        if not result.completion.ok:raise ValueError()
        if config['vision'] and (result.completion.observed_color or '').strip().lower()!='blue':raise VisionProbeFailed()
        runtime,_=await browser_runtime()
        usage=getattr(result,'usage',None)
        return {'ok':True,'vision_tested':config['vision'],'browser':runtime,'capabilities':{'structured_output':True,'image_payload_accepted':config['vision'],'visual_recognition_tested':config['vision'],'action_schema_tested':True,'browser_actions_tested':False},'usage':usage.model_dump() if hasattr(usage,'model_dump') else None}
    except Exception as e:
        if engine.proxy_config.get('enabled') and engine.proxy_config.get('scope')=='application' and engine.proxy.last_error:
            error=engine.proxy.last_error
            raise HTTPException(502,error['code']+': '+error['message']) from None
        from diagnostics import model_error
        code,message=model_error(e)
        raise HTTPException(502,code+': '+message) from None

@app.get('/sw.js')
def worker():return FileResponse(ROOT/'static/sw.js',media_type='application/javascript')

@app.get('/')
def index():return FileResponse(ROOT/'static/index.html')
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
