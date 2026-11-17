import json
from datetime import timedelta
from sqlalchemy import func, select
from market import retention
from market.db import now
from market.ingest import ingest
from market.models import DailyObservation, Listing, Market, Observation, RetentionPolicy, RetentionPolicyChange, Snapshot, SnapshotStatistic
from market.pricing import daily_history, values


def seed(database):
    at=now().replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=1)
    with database.begin() as db:
        m=Market(region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Synthetic retention fixture')
        db.add(m);db.flush()
        for index,days in enumerate([600,500,426,424,400,366,365,100,90,70,60,30,14,8,2,0]):
            stamp=at-timedelta(days=days)
            ingest(db,m.id,json.dumps({'auctions':[{'id':index+1,'item':{'id':25},'buyout':100+index,'quantity':1}]}).encode(),request_key=f'fixture-{index}',retrieved_at=stamp,synthetic=True)
        market=m.id
        variant=db.scalar(select(SnapshotStatistic.variant_key))
    return at,market,variant


def authorize(database,monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET','synthetic-retention-signing-key-32-characters')
    monkeypatch.setattr(retention,'backup_ready',lambda:True)
    with database.begin() as db:
        policy=retention.policy_view(db)
        row=RetentionPolicy(id=1,revision=0,approved_hash=policy['policy_hash'])
        db.add(row)


def test_preview_is_readonly_and_requires_separate_approval(owner,database,monkeypatch):
    seed(database)
    monkeypatch.setenv('SYNC_CURSOR_SECRET','synthetic-retention-signing-key-32-characters')
    before=owner.get('/api/v1/admin/retention/preview')
    assert before.status_code==200
    report=before.json()
    assert report['status']=='dry_run' and report['policy']['raw_days']==7
    assert report['policy']['intraday_days']==90 and report['policy']['daily_days']==365
    assert report['filesystem_recoverable_bytes'] is None
    assert report['next_stage']=='daily_references'
    assert owner.post('/api/v1/admin/retention/apply',json={'confirmation':report['confirmation'],'confirm':True}).status_code==409
    with database() as db:assert db.scalar(select(func.count()).select_from(Observation))==16


def test_policy_changes_audited_and_invalidate_authorization(owner,database,monkeypatch):
    authorize(database,monkeypatch)
    body={'raw_days':7,'intraday_days':90,'daily_days':365,'operational_days':180,'security_days':365}
    response=owner.patch('/api/v1/admin/retention',json=body)
    assert response.status_code==200 and not response.json()['application_authorized']
    with database() as db:
        change=db.scalar(select(RetentionPolicyChange))
        assert json.loads(change.after)==body and db.get(RetentionPolicy,1).approved_hash is None
    assert owner.patch('/api/v1/admin/retention',json={**body,'intraday_days':30}).status_code==422
    assert owner.patch('/api/v1/admin/retention',json={**body,'raw_days':180}).status_code==422


def test_staged_compaction_preserves_prices_support_current_and_bounded_rows(owner,database,monkeypatch):
    at,market,variant=seed(database)
    with database() as db:
        before=values(db,market,25,variant)
        chart=daily_history(db,market,25,variant,365)
    authorize(database,monkeypatch)
    monkeypatch.setattr(retention,'BATCH_ROWS',2)
    totals={}
    for _ in range(100):
        report=owner.get('/api/v1/admin/retention/preview').json()
        if report['next_stage'] is None:break
        response=owner.post('/api/v1/admin/retention/apply',json={'confirmation':report['confirmation'],'confirm':True})
        assert response.status_code==200,response.text
        result=response.json();assert 0<result['rows_removed']<=2
        totals[result['stage']]=totals.get(result['stage'],0)+result['rows_removed']
    else:assert False,'Compaction failed to finish'
    assert totals['daily_references']>=3 and totals['raw_listings']>0
    with database() as db:
        assert values(db,market,25,variant)==before
        after=daily_history(db,market,25,variant,365)
        assert after==chart
        current=db.scalar(select(Observation).order_by(Observation.retrieved_at.desc()).limit(1))
        assert db.get(Snapshot,current.snapshot_id).raw_retained
        assert db.get(DailyObservation,(market,(at-timedelta(days=400)).date())) is not None
        assert db.scalar(select(func.count()).select_from(Observation))<16


def test_confirmation_tampering_and_policy_change_rejected(owner,database,monkeypatch):
    seed(database);authorize(database,monkeypatch)
    report=owner.get('/api/v1/admin/retention/preview').json()
    assert owner.post('/api/v1/admin/retention/apply',json={'confirmation':report['confirmation']+'bad','confirm':True}).status_code==409
    assert owner.post('/api/v1/admin/retention/apply',json={'confirmation':report['confirmation'],'confirm':False}).status_code==409
    owner.patch('/api/v1/admin/retention',json={'daily_days':730})
    assert owner.post('/api/v1/admin/retention/apply',json={'confirmation':report['confirmation'],'confirm':True}).status_code==409


def test_compacted_daily_support_invalidates_old_cursor_and_full_sync_recovers(owner,database,monkeypatch):
    at,market,variant=seed(database)
    authorize(database,monkeypatch)
    from market.sync_api import encode_cursor
    with database() as db:
        old=db.scalar(select(Observation).order_by(Observation.retrieved_at).limit(1))
        cursor=encode_cursor({'v':1,'market':market,'base':0,'target':old.id,'after':[0,''],'done':True})
    report=owner.get('/api/v1/admin/retention/preview').json()
    assert owner.post('/api/v1/admin/retention/apply',json={'confirmation':report['confirmation'],'confirm':True}).status_code==200
    assert owner.get(f'/api/v1/sync/markets/{market}?cursor={cursor}').status_code==409
    response=owner.get(f'/api/v1/sync/markets/{market}')
    assert response.status_code==200 and response.json()['changes']


def test_partial_raw_compaction_can_rehydrate_repeated_snapshot(database):
    with database.begin() as db:
        m=Market(region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Partial fixture')
        db.add(m);db.flush()
        body=json.dumps({'auctions':[{'id':i,'item':{'id':25},'buyout':100,'quantity':1} for i in range(1,4)]}).encode()
        obs=ingest(db,m.id,body,request_key='before-partial',synthetic=True)
        snapshot=db.get(Snapshot,obs.snapshot_id);snapshot.raw_retained=False;snapshot.statistics_retained=False
        # Retain actual raw/statistic remnants as after a bounded first batch.
        ident=m.id;snap=snapshot.id
    with database.begin() as db:
        obs=ingest(db,ident,body,request_key='after-partial',synthetic=True)
        assert obs.snapshot_id==snap
        assert db.scalar(select(func.count()).select_from(Listing).where(Listing.snapshot_id==snap))==3
        assert db.scalar(select(func.count()).select_from(SnapshotStatistic).where(SnapshotStatistic.snapshot_id==snap))==1


def test_apply_rejects_absent_backup_even_with_approved_policy(owner,database,monkeypatch):
    seed(database);authorize(database,monkeypatch)
    report=owner.get('/api/v1/admin/retention/preview').json()
    monkeypatch.setattr(retention,'backup_ready',lambda:False)
    assert owner.post('/api/v1/admin/retention/apply',json={'confirmation':report['confirmation'],'confirm':True}).status_code==409


def test_backup_gate_binds_restoration_to_the_current_archive(monkeypatch):
    stamp=now();created=stamp-timedelta(minutes=1)
    state={'status':'ok','last_success':created.isoformat(),'last_restoration_verified_at':stamp.isoformat(),
        'filename':'market-fixture.dump','restored_archive_filename':'market-fixture.dump',
        'restored_archive_created_at':created.isoformat(),'restored_archive_sha256':'a'*64}
    monkeypatch.setattr('market.market_api.backup_state',lambda:state)
    assert retention.backup_ready()
    state['filename']='new-unrestored-archive.dump'
    assert not retention.backup_ready()
    state['filename']='market-fixture.dump';state['restored_archive_sha256']='invalid'
    assert not retention.backup_ready()


def test_real_batch_cap_exact_removal_replay_and_resume(owner, database, monkeypatch):
    """6,201 eligible raw rows cross the actual 5,000-row transaction boundary."""
    at = now()
    with database.begin() as db:
        market = Market(region='us', ruleset_id=2, house_id=114, source_kind='auctions', label='Synthetic batch boundary')
        db.add(market); db.flush(); market_id = market.id
        old = ingest(db, market_id, json.dumps({'auctions':[
            {'id':i, 'item':{'id':25}, 'buyout':100, 'quantity':1} for i in range(1,6202)
        ]}).encode(), request_key='batch-old', retrieved_at=at-timedelta(days=10), synthetic=True)
        old_snapshot = old.snapshot_id
        current = ingest(db, market_id, b'{"auctions":[{"id":7000,"item":{"id":25},"buyout":200,"quantity":1}]}',
                         request_key='batch-current', retrieved_at=at, synthetic=True)
        current_snapshot = current.snapshot_id
        variant = db.scalar(select(SnapshotStatistic.variant_key))
        baseline = values(db,market_id,25,variant)
    authorize(database, monkeypatch)
    first = owner.get('/api/v1/admin/retention/preview').json()
    assert first['next_stage'] == 'raw_listings' and first['next_batch_rows'] == 5000
    applied = owner.post('/api/v1/admin/retention/apply', json={'confirmation':first['confirmation'],'confirm':True})
    assert applied.json()['rows_removed'] == 5000
    assert owner.post('/api/v1/admin/retention/apply', json={'confirmation':first['confirmation'],'confirm':True}).status_code == 409
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Listing).where(Listing.snapshot_id == old_snapshot)) == 1201
        assert db.scalar(select(func.count()).select_from(Listing).where(Listing.snapshot_id == current_snapshot)) == 1
        assert values(db,market_id,25,variant) == baseline
    # A later independent preview resumes from persisted state; no in-memory task state.
    second = owner.get('/api/v1/admin/retention/preview').json()
    assert second['next_batch_rows'] == 1201
    assert owner.post('/api/v1/admin/retention/apply', json={'confirmation':second['confirmation'],'confirm':True}).json()['rows_removed'] == 1201
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Listing)) == 1
        assert values(db,market_id,25,variant) == baseline
    state = owner.get('/api/v1/admin/retention').json()
    assert state['completed_batches'] == 2 and state['scheduled'] is False
