"""Read-only fixed-clock parity probe; isolated restored market_test only.

Mount predecessor tracker source at /previous.py (git show f87ae6b:backend/market/recovery_tracker.py).
No provider access, grants or rows are created.
"""
import importlib.util,json,time
from datetime import datetime,timezone
from market.db import Session,engine
from sqlalchemy import text
if engine.dialect.name != "postgresql" or engine.url.database != "market_test":raise SystemExit("Isolated market_test required")
import market.recovery_tracker as current
from market.metadata_recovery import latest_foreverdb_build
spec=importlib.util.spec_from_file_location('market._previous_tracker','/previous.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
fixed=datetime(2026,11,17,19,48,tzinfo=timezone.utc)
current.now=old.now=lambda:fixed
with Session() as db:
 db.execute(text("SET TRANSACTION READ ONLY"))
 results=[]
 for module in (old,current):
  started=time.monotonic();data=module.tracker(market_id=2,q='',missing='all',provider=None,eligibility='all',outcome=None,sort='item_id',desc=False,offset=0,limit=25,user=None,db=db)
  results.append({'summary':data['summary'],'total':data['total'],'ids':[r['item_id'] for r in data['rows']],'seconds':round(time.monotonic()-started,3)})
 assert results[0]['summary']==results[1]['summary'],results
 assert results[0]['ids']==results[1]['ids'] and results[0]['total']==results[1]['total']
 db.rollback()
 print(json.dumps({'clock':fixed.isoformat(),'same_restored_population':True,'external_requests':0,'results':results}))
