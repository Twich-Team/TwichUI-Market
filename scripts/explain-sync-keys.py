"""Compare exact legacy and bounded-union keyset queries on market_test only."""
import json, os
from pathlib import Path
from sqlalchemy import and_,or_,select,text,tuple_,union
from market.db import engine
from market.models import SnapshotStatistic as S

assert engine.url.database=='market_test'
data=json.loads(Path(os.environ['SYNC_PERF_FIXTURE']).read_bytes())
observations=data['observations'];sids=sorted({o['snapshot_id'] for o in observations if o['id']>=data['full_target']})
assert len(sids)==2
columns=[S.item_id,S.variant_key]
results=[]
with engine.connect() as db:
    db.execute(text("SET LOCAL statement_timeout='3s'"))
    n=db.scalar(select(__import__('sqlalchemy').func.count()).select_from(S).where(S.snapshot_id==sids[-1]))
    for offset in [0,n//2,n-100]:
        after=(0,'') if offset==0 else tuple(db.execute(select(*columns).where(S.snapshot_id==sids[-1]).order_by(*columns).offset(offset).limit(1)).one())
        old=select(*columns).where(S.snapshot_id.in_(sids),or_(S.item_id>after[0],and_(S.item_id==after[0],S.variant_key>after[1]))).distinct().order_by(*columns).limit(101)
        candidates=[select(*columns).where(S.snapshot_id==sid,tuple_(*columns)>after).order_by(*columns).limit(101) for sid in sids]
        new=union(*candidates).order_by('item_id','variant_key').limit(101)
        assert list(db.execute(old))==list(db.execute(new))
        for repeat in range(3):
            for label,query in [('legacy',old),('bounded_union',new)]:
                sql=str(query.compile(engine,compile_kwargs={'literal_binds':True}))
                plan=db.execute(text('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+sql)).scalar_one()[0]
                results.append({'offset':offset,'repeat':repeat,'query':label,'plan':plan})
print(json.dumps(results))
