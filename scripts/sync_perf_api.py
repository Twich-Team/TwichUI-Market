"""Isolated baseline profiler around unmodified production sync functions.

No SQL text, parameters, paths with IDs, credentials, cursors or response contents
are retained. Control routes are fixture-only and never imported by market.app.
"""
import contextvars,functools,inspect,json,os,time,resource,threading
from collections import defaultdict
from pathlib import Path
from fastapi import Request,Depends
from sqlalchemy import event,select,insert,delete
from sqlalchemy.orm import Session as OrmSession
from market.app import app as original_app
from market.db import engine,Session,session
from market import security,sync_api,sync_generation
from market.models import Observation
from starlette.responses import JSONResponse
assert engine.url.database=='market_test' and os.environ.get('SYNC_PERFORMANCE_FIXTURE')=='true'
active=contextvars.ContextVar('sync_performance',default=None)
records=[];lock=threading.Lock()
def measured(label,fn):
    @functools.wraps(fn)
    def wrapped(*args,**kwargs):
        trace=active.get();start=time.perf_counter()
        if trace is not None:old=trace['stage'];trace['stage']=label
        try:return fn(*args,**kwargs)
        finally:
            if trace is not None:trace['stages'][label]+=1000*(time.perf_counter()-start);trace['stage']=old
    return wrapped
sync_generation.signature=measured('historical_signatures',sync_generation.signature)
_compact=sync_api.compact_many
def compact(db,observation,keys,generation):
    trace=active.get()
    if trace is not None:trace['keys_scanned']=max(trace.get('keys_scanned',0),len(keys))
    return _compact(db,observation,keys,generation)
sync_api.compact_many=measured('pricing',compact)
JSONResponse.render=measured('json_serialization',JSONResponse.render)
def identity(request:Request,db:OrmSession=Depends(session)):
    return measured('authentication',security.identity)(request,db)
original_app.dependency_overrides[security.identity]=identity
@event.listens_for(engine,'before_cursor_execute')
def before(connection,cursor,statement,parameters,context,many):
    context._sync_perf_start=time.perf_counter()
@event.listens_for(engine,'after_cursor_execute')
def after(connection,cursor,statement,parameters,context,many):
    trace=active.get()
    if trace is None:return
    elapsed=1000*(time.perf_counter()-context._sync_perf_start)
    trace['queries']+=1;trace['sql_ms']+=elapsed
    category=('watermark_lock' if 'pg_advisory_xact_lock' in statement else trace['stage'])
    trace['sql_by_stage'][category]+=elapsed
@original_app.get('/__sync_perf/report')
def report():
    with lock:result=list(records);records.clear()
    return {'requests':result,'rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
@original_app.post('/__sync_perf/reset')
def reset():
    data=json.loads(Path(os.environ['SYNC_PERF_FIXTURE']).read_bytes())
    with Session.begin() as db:
        db.execute(delete(Observation).where(Observation.id>data['full_target']))
    return {'fixture_only':True,'target':data['full_target']}
@original_app.post('/__sync_perf/advance/{target}')
def advance(target:int):
    data=json.loads(Path(os.environ['SYNC_PERF_FIXTURE']).read_bytes())
    from datetime import datetime
    with Session.begin() as db:
        saved=set(db.scalars(select(Observation.id)))
        rows=[dict(r) for r in data['observations'] if r['id']<=target and r['id'] not in saved]
        for r in rows:r['retrieved_at']=datetime.fromisoformat(r['retrieved_at'])
        if rows:db.execute(insert(Observation),rows)
    return {'added':len(rows)}
class Profiled:
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['path'].startswith('/__sync_perf/'):
            return await original_app(scope,receive,send)
        trace={'stage':'other','queries':0,'sql_ms':0.,'sql_by_stage':defaultdict(float),'stages':defaultdict(float),'bytes':0,'status':0}
        token=active.set(trace);start=time.perf_counter();cpu=time.process_time()
        async def measured_send(message):
            if message['type']=='http.response.start':trace['status']=message['status']
            if message['type']=='http.response.body':trace['bytes']+=len(message.get('body',b''))
            await send(message)
        try:await original_app(scope,receive,measured_send)
        finally:
            active.reset(token);trace.pop('stage',None)
            trace.update(elapsed_ms=1000*(time.perf_counter()-start),cpu_ms=1000*(time.process_time()-cpu),kind='sync' if '/sync/' in scope['path'] else 'other')
            with lock:
                if len(records)<20000:records.append(trace)
app=Profiled()
