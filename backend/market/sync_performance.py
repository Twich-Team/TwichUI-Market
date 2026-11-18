"""Opt-in fixed-field sync diagnostics; no SQL text, parameters, cursors or logging.

Both operator configuration and the authenticated client's request opt-in are
required. Only successful price-sync replies expose numeric diagnostic headers.
"""
import contextvars
from contextlib import contextmanager
from functools import wraps
import os,re,time
from sqlalchemy import event
from sqlalchemy.engine import Engine
from starlette.responses import JSONResponse

current=contextvars.ContextVar('sync_performance',default=None)
STAGES=('authentication','watermark','history','pricing','keys','changes','json','sql','lock','total','cpu')

@contextmanager
def timing(stage):
    trace=current.get()
    if trace is None:
        yield
        return
    start=time.perf_counter();old=trace['stage'];trace['stage']=stage
    try:yield
    finally:
        trace['ms'][stage]=trace['ms'].get(stage,0)+1000*(time.perf_counter()-start)
        trace['stage']=old

def timed(stage):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            with timing(stage):return fn(*args,**kwargs)
        return wrapped
    return decorate

def count(name,value):
    trace=current.get()
    if trace is not None and name in ('scanned','changed','bytes'):
        trace[name]=min(2**32-1,trace.get(name,0)+value)

@event.listens_for(Engine,'before_cursor_execute')
def sql_start(connection,cursor,statement,parameters,context,many):
    if current.get() is not None:context._sync_timing=time.perf_counter()

@event.listens_for(Engine,'after_cursor_execute')
def sql_end(connection,cursor,statement,parameters,context,many):
    trace=current.get();start=getattr(context,'_sync_timing',None)
    if trace is None or start is None:return
    elapsed=1000*(time.perf_counter()-start);trace['queries']+=1
    trace['ms']['sql']=trace['ms'].get('sql',0)+elapsed
    if 'pg_advisory_xact_lock' in statement:trace['ms']['lock']=trace['ms'].get('lock',0)+elapsed
    if trace['stage']=='pricing':trace['pricing_sql_ms']+=elapsed

class SyncJSONResponse(JSONResponse):
    def render(self,content):
        with timing('json'):body=super().render(content)
        count('bytes',len(body))
        return body

class SyncTimingMiddleware:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        enabled=(scope['type']=='http' and scope.get('method')=='GET'
            and os.environ.get('SYNC_PERFORMANCE_DIAGNOSTICS')=='true'
            and re.fullmatch(r'/api/v1/sync/markets/[0-9]+',scope.get('path',''))
            and any(k==b'x-companion-sync-timing' and v==b'1' for k,v in scope.get('headers',[])))
        if not enabled:return await self.app(scope,receive,send)
        trace={'ms':{},'queries':0,'stage':'other','pricing_sql_ms':0.}
        token=current.set(trace);start=time.perf_counter();cpu=time.process_time()
        async def measured_send(message):
            if message['type']=='http.response.start' and message['status']==200:
                trace['ms']['total']=1000*(time.perf_counter()-start)
                trace['ms']['cpu']=1000*(time.process_time()-cpu)
                trace['ms']['calculation']=max(0.,trace['ms'].get('pricing',0)-trace['pricing_sql_ms'])
                stages=STAGES+('calculation',)
                headers=[(b'server-timing',','.join(f'{k};dur={trace["ms"][k]:.3f}' for k in stages if k in trace['ms']).encode()),
                    (b'x-companion-sync-counts',f'queries={trace["queries"]};scanned={trace.get("scanned",0)};changed={trace.get("changed",0)};bytes={trace.get("bytes",0)}'.encode())]
                message={**message,'headers':list(message.get('headers',[]))+headers}
            await send(message)
        try:return await self.app(scope,receive,measured_send)
        finally:current.reset(token)
