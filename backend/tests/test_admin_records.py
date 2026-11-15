"""Real query, permission and redaction checks on isolated test databases."""
from datetime import timedelta
import json
from sqlalchemy import select
from market.db import now
from market.models import MetadataProvider, MetadataTask, SecurityEvent, User
from market.metadata_recovery import enqueue
from market.security import hasher
from test_metadata_recovery import setup, response


def test_attempts_filter_summary_and_no_http_success_claim(owner, database):
    market=setup(database)
    with database.begin() as db:
        job,_=enqueue(db,market,'missing',['everloot'],budget=2)
        tasks=list(db.scalars(select(MetadataTask).where(MetadataTask.job_id==job.id).order_by(MetadataTask.id)))
        for task in tasks:
            task.state='completed';task.attempts=1
        tasks[0].result_json=json.dumps({'status':'available','http_status':200,'recovered_fields':[], 'raw':'evl_never_return_me'})
        tasks[1].result_json=json.dumps({'status':'forbidden','http_status':403,'headers':{'Authorization':'Bearer evl_never_return_me'}})
    result=owner.get(f'/api/v1/admin/records/metadata-attempts?market_id={market}&limit=1').json()
    assert result['total']==2 and len(result['rows'])==1
    assert result['summary']=={'no_usable_data':1,'access_blocked':1}
    assert 'evl_never_return_me' not in json.dumps(result)
    filtered=owner.get('/api/v1/admin/records/metadata-attempts?outcome=access_blocked').json()
    assert filtered['total']==1 and filtered['rows'][0]['http_status']==403
    assert 'name_recovered' not in result['summary']
    assert owner.get('/api/v1/admin/records/metadata-attempts?sort=credential').status_code==422
    assert owner.get('/api/v1/admin/records/metadata-attempts?outcome=invented').status_code==422
    assert owner.get('/api/v1/admin/records/metadata-attempts?limit=101').status_code==422


def test_retry_guard_and_dedupe(owner,database):
    market=setup(database)
    with database.begin() as db:
        job,_=enqueue(db,market,'single',['everloot'],item_id=720,budget=1)
        job.state='completed'
        task=db.scalar(select(MetadataTask).where(MetadataTask.job_id==job.id));task.state='completed'
        ident=task.id
        provider=db.get(MetadataProvider,'everloot');provider.cooldown_until=now()+timedelta(hours=1)
    assert owner.post(f'/api/v1/admin/records/metadata-attempts/{ident}/retry').status_code==409
    with database.begin() as db: db.get(MetadataProvider,'everloot').cooldown_until=None
    assert owner.post(f'/api/v1/admin/records/metadata-attempts/{ident}/retry').status_code==202
    assert owner.post(f'/api/v1/admin/records/metadata-attempts/{ident}/retry').status_code==409


def test_security_pagination_and_member_permissions(owner,database,client):
    with database.begin() as db:
        db.add_all([SecurityEvent(action='metadata.test',detail='provider=everloot') for _ in range(31)])
        db.add(User(username='records_member',password_hash=hasher.hash('correct horse battery'),role='member'))
    page=owner.get('/api/v1/admin/records/security?category=metadata&limit=25').json()
    assert page['total']==31 and len(page['rows'])==25
    second=owner.get('/api/v1/admin/records/security?category=metadata&offset=25').json()
    assert len(second['rows'])==6
    assert not set(row['id'] for row in page['rows'])&set(row['id'] for row in second['rows'])
    client.headers.pop('x-csrf-token',None)
    client.post('/api/v1/auth/login',json={'username':'records_member','password':'correct horse battery'})
    for path in ('security','collection','metadata-attempts','jobs','unresolved?market_id=1'):
        assert client.get('/api/v1/admin/records/'+path).status_code==403


def test_unresolved_joins_and_job_pages(owner,database):
    market=setup(database)
    result=owner.get(f'/api/v1/admin/records/unresolved?market_id={market}').json()
    assert result['total']==2 and [r['item_id'] for r in result['rows']]==[720,721]
    assert result['rows'][0]['supplemental_status']=='Not attempted'
    assert owner.get(f'/api/v1/admin/records/unresolved?market_id={market}&item_id=721').json()['total']==1
    assert owner.get('/api/v1/admin/records/jobs').status_code==200
    assert owner.get('/api/v1/admin/records/collection').status_code==200


def test_recovery_measures_real_field_gains(database):
    from market.metadata_recovery import tick
    market=setup(database)
    with database.begin() as db: enqueue(db,market,'single',['everloot'],item_id=720,budget=1)
    tick(database,fetcher=lambda *a,**k:response(),automatic=False)
    with database() as db:
        task=db.scalar(select(MetadataTask))
        result=json.loads(task.result_json)
        assert result['outcome']=='name_recovered' and result['new_fields']==['name']


def test_catalog_diagnostics_are_not_failed_item_recoveries(owner,database):
    market=setup(database)
    with database.begin() as db:
        job,_=enqueue(db,market,'single',['everloot'],item_id=720,budget=1)
        job.mode='diagnostic';job.state='completed'
        task=db.scalar(select(MetadataTask).where(MetadataTask.job_id==job.id));task.state='completed'
        task.result_json=json.dumps({'kind':'corpus_page','status':'observations_only','outcome':'no_usable_data','http_status':200})
    result=owner.get('/api/v1/admin/records/metadata-attempts').json()
    assert result['rows'][0]['record_scope']=='catalog'
    assert result['rows'][0]['outcome']=='observations_returned'
    assert result['summary']=={'observations_returned':1}


def test_failed_collection_without_detail_is_still_in_failure_history(owner,database):
    from market.models import CollectionRun
    market=setup(database)
    with database.begin() as db:db.add(CollectionRun(market_id=market,status='failed',http_status=None,error=None))
    value=owner.get('/api/v1/admin/records/collection?status=failures').json()
    assert value['total']==1 and value['rows'][0]['status']=='failed'
