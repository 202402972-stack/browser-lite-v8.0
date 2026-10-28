"""Provider-reported usage only. Limits are checked before the next logical call."""
import time,uuid
from browser_use.llm.views import ChatInvokeUsage

class BudgetExceeded(RuntimeError):pass

def compaction_settings(config,model):
    from browser_use.agent.views import MessageCompactionSettings
    # Use only the char threshold: upstream revalidates settings and its token
    # convenience field would populate both mutually exclusive thresholds.
    return MessageCompactionSettings(compact_every_n_steps=1,
        trigger_char_count=int(config.get('context_window',32768)*.7*4),
        keep_last_items=8,summary_max_chars=6000,compaction_llm=model)

def normalized_usage(raw):
    if raw is None:return None
    def value(obj,key,default=None):
        return obj.get(key,default) if isinstance(obj,dict) else getattr(obj,key,default)
    prompt=value(raw,'prompt_tokens',value(raw,'input_tokens'))
    completion=value(raw,'completion_tokens',value(raw,'output_tokens'))
    if not isinstance(prompt,int) or not isinstance(completion,int) or min(prompt,completion)<0:return None
    cached=value(raw,'cached_input_tokens',value(value(raw,'prompt_tokens_details',{}),'cached_tokens'))
    return ChatInvokeUsage(prompt_tokens=prompt,completion_tokens=completion,total_tokens=prompt+completion,
        prompt_cached_tokens=min(prompt,cached) if isinstance(cached,int) and cached>=0 else None,
        prompt_cache_creation_tokens=None,prompt_image_tokens=None)

class UsageLedger:
    def __init__(self,engine):self.engine=engine;self.blocked=None
    def data(self):
        return self.engine.task.setdefault('usage',{'calls':0,'reported_calls':0,'unknown_calls':0,
            'prompt_tokens':0,'completion_tokens':0,'cached_tokens':0,'total_tokens':0,
            'known_cost_usd':0.0,'priced_calls':0,'recent':[]})
    def check(self):
        data=self.data();limits=self.engine.task.get('limits') or {}
        reason=None
        if any(v is not None for v in limits.values()) and data['unknown_calls']:
            reason='توقفنا لأن استهلاك أحد الطلبات غير متاح؛ لا يمكن التحقق من السقف. أزل السقف أو ابدأ مهمة جديدة.'
        elif limits.get('token_limit') is not None and data['total_tokens']>=limits['token_limit']:
            reason='وصلت المهمة لسقف التوكنز؛ التقدم محفوظ. ارفع السقف من الإعدادات ثم استكمل.'
        elif limits.get('cost_limit_usd') is not None and data['priced_calls']<data['reported_calls']:
            reason='توقفنا لأن سعر أحد الطلبات غير متاح؛ أزل سقف التكلفة أو ابدأ مهمة جديدة بسعر موثق.'
        elif limits.get('cost_limit_usd') is not None and data['known_cost_usd']>=limits['cost_limit_usd']:
            reason='وصلت المهمة لسقف التكلفة التقديري؛ التقدم محفوظ. ارفع السقف ثم استكمل.'
        if reason:
            self.blocked=reason
            raise BudgetExceeded(reason)
    def begin(self,config):
        self.check();data=self.data();identifier=uuid.uuid4().hex
        entry={'id':identifier,'provider':config['provider'],'model':config['model'],'time':time.time(),'status':'pending','usage':None,'cost_usd':None}
        data['calls']+=1;data['unknown_calls']+=1
        data['recent']=(data['recent']+[entry])[-30:]
        self.engine.update(usage=data)
        return entry
    def finish(self,entry,usage,config,status='completed',elapsed_ms=None):
        data=self.data();entry['status']=status
        if elapsed_ms is not None:entry['elapsed_ms']=max(0,elapsed_ms)
        if usage is not None:
            raw=usage.model_dump() if hasattr(usage,'model_dump') else usage
            entry['usage']={k:raw.get(k) for k in ('prompt_tokens','completion_tokens','total_tokens','prompt_cached_tokens')}
            data['unknown_calls']-=1;data['reported_calls']+=1
            for k in ('prompt_tokens','completion_tokens','total_tokens'):data[k]+=raw[k]
            cached=raw.get('prompt_cached_tokens') or 0;data['cached_tokens']+=cached
            pricing=config.get('pricing')
            if pricing and pricing.get('input') is not None and pricing.get('output') is not None:
                cost=((raw['prompt_tokens']-cached)*pricing['input']+cached*(pricing.get('cached_input') if pricing.get('cached_input') is not None else pricing['input'])+raw['completion_tokens']*pricing['output'])/1_000_000
                entry['cost_usd']=cost;entry['pricing']=pricing
                data['known_cost_usd']+=cost;data['priced_calls']+=1
        self.engine.update(usage=data)
    def public(self):
        data=dict(self.data());complete=data['unknown_calls']==0
        data['measurement']=('complete' if complete else 'partial') if data['calls'] else 'not_recorded'
        data['estimated_cost_usd']=data['known_cost_usd'] if data['calls'] and complete and data['priced_calls']==data['calls'] else None
        data['limits']=self.engine.task.get('limits',{})
        data['note']='Provider-reported logical calls; hidden SDK retries and failed unreported requests may incur additional charges. Limits are not a billing guarantee.'
        return data

class MeteredModel:
    def __init__(self,inner,ledger,config):self.inner=inner;self.ledger=ledger;self.config=config
    def __getattr__(self,name):return getattr(self.inner,name)
    async def ainvoke(self,*args,**kwargs):
        entry=self.ledger.begin(self.config)
        started=time.monotonic()
        try:
            result=await self.inner.ainvoke(*args,**kwargs)
        except BaseException as exc:
            self.ledger.finish(entry,getattr(exc,'consumed_usage',None),self.config,'failed',round((time.monotonic()-started)*1000))
            raise
        self.ledger.finish(entry,getattr(result,'usage',None),self.config,elapsed_ms=round((time.monotonic()-started)*1000))
        return result
