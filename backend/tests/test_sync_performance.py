"""Diagnostics are separately opted in, authenticated, fixed-field and data-neutral."""
import json
from market.ingest import ingest
from market.models import Market


def test_sync_timing_headers_require_operator_client_and_successful_auth(owner,database,monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET','performance-fixture-secret-over-thirty-two')
    with database.begin() as db:
        m=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Synthetic performance fixture',verified=True)
        db.add(m);db.flush();mid=m.id
        ingest(db,mid,json.dumps({'auctions':[{'id':1,'item':{'id':2589},'quantity':3,'buyout':200}]}).encode(),request_key='perf',synthetic=True)
    path=f'/api/v1/sync/markets/{mid}'
    standard=owner.get(path);assert standard.status_code==200
    assert 'server-timing' not in standard.headers
    assert 'server-timing' not in owner.get(path,headers={'X-Companion-Sync-Timing':'1'}).headers
    monkeypatch.setenv('SYNC_PERFORMANCE_DIAGNOSTICS','true')
    assert 'server-timing' not in owner.get(path).headers
    measured=owner.get(path,headers={'X-Companion-Sync-Timing':'1'})
    assert measured.json()==standard.json()
    assert 'sql;dur=' in measured.headers['server-timing'] and 'authentication;dur=' in measured.headers['server-timing']
    assert 'scanned=1;changed=1;' in measured.headers['x-companion-sync-counts']
    assert all(name not in str(measured.headers) for name in ['Bearer','token_hash','request_key'])
    owner.cookies.clear();owner.headers.pop('authorization',None)
    denied=owner.get(path,headers={'X-Companion-Sync-Timing':'1'});assert denied.status_code==401
    assert 'server-timing' not in denied.headers
