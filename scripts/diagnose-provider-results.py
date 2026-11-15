"""Bounded read-only provider-attempt diagnostics; no provider requests or sessions.

Uses the existing rootless production operator path. Emits only aggregate counts
and the safe administrator response allowlist. Never exports provider payloads,
credentials, account records or arbitrary exception text.
"""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Compile the candidate query in a separate Python process against a database
    # transaction that PostgreSQL itself enforces as read-only. Running services
    # and their modules are never modified.
    source = (ROOT / 'backend/market/admin_records.py').read_text()
    script = '''
import json,time,types
from sqlalchemy import select,func,text
from market.db import Session
from market.models import MetadataTask,MetadataJob,MetadataSource
candidate=types.ModuleType('market.candidate_records');candidate.__package__='market'
exec(SOURCE,candidate.__dict__)
with Session() as db:
    assert db.scalar(text('SHOW transaction_read_only'))=='on'
    scopes=[]
    for market in [None,1,2]:
        started=time.monotonic()
        result=candidate.attempts(market_id=market,provider=None,outcome=None,item_id=None,since=None,until=None,q='',offset=0,limit=25,sort='at',desc=True,user=None,db=db)
        scopes.append({'market_id':market,'total':result['total'],'summary':result['summary'],'handler_ms':round((time.monotonic()-started)*1000,2),'sample':[{key:row[key] for key in ('id','provider','item_id','outcome','fields_returned','fields_recovered','delta_recorded')} for row in result['rows'][:3]]})
    source_counts=[{'provider':p,'status':s,'count':n} for p,s,n in db.execute(select(MetadataSource.provider,MetadataSource.status,func.count()).group_by(MetadataSource.provider,MetadataSource.status))]
    print(json.dumps({'read_only':True,'scope':'Actual persisted production records; candidate GET handler, no HTTP authentication bypass claim. Authentication/redaction verified separately in isolated suites. Counts may change through the existing worker.','scopes':scopes,'source_current_record_counts':source_counts},sort_keys=True))
'''.replace('exec(SOURCE,', 'exec(' + repr(source) + ',')
    output = subprocess.check_output([
        'docker', '--context', 'rootless', 'exec', '-i', '-e',
        'PGOPTIONS=-c default_transaction_read_only=on -c statement_timeout=10000',
        'twichui-market-api-1', 'python', '-'], input=script, text=True)
    print(json.dumps(json.loads(output), indent=2))


if __name__ == '__main__':
    main()
