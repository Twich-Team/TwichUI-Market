import json
from datetime import timedelta
import pytest
from sqlalchemy import func, select, text
from fastapi import HTTPException
from market.db import now
from market.models import (Market, RetentionPolicy, RetentionAutomation, RetentionExecution, RetentionBatch, User, Listing, Observation)
from market.retention import PolicyInput, update_policy
from market.retention_worker import (Limits, authorization_document, authorize_automatic, approved_document, work_once, enable, EnableInput)
from market.ingest import ingest, canonical


@pytest.fixture
def automation(database, monkeypatch):
    monkeypatch.setattr('market.retention.backup_ready',lambda:True)
    monkeypatch.setattr('market.retention_worker.recovery_ready',lambda _:True)
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='isolated retention fixture',enabled=False,verified=True)
        db.add(market);db.flush()
        db.add(RetentionPolicy(id=1,revision=2));db.flush()
        # Distinct old snapshots followed by a protected current head.
        for n in range(4):
            body=canonical({'auctions':[{'id':n*250+i+1,'item':{'id':123},'quantity':3,'buyout':1001} for i in range(250)]}).encode()
            ingest(db,market.id,body,request_key=str(n),retrieved_at=now()-timedelta(days=20-n),synthetic=True)
        actor=db.get(User,1)
        document=authorization_document(db,Limits(rows_per_batch=100,max_batches=2))
        authorize_automatic(db,actor,'Synthetic fixture approval only',limits=Limits(rows_per_batch=100,max_batches=2),expected_execution_hash=document['execution_hash'])
        state=db.get(RetentionAutomation,1);state.enabled=True;state.next_run_at=now()
    return document


def require_pg(database):
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL scheduler concurrency')


def test_inactive_service_never_authorizes_or_deletes(database):
    require_pg(database)
    assert work_once(database)['status']=='inactive'
    with database() as db:
        assert db.get(RetentionAutomation,1) is None
        assert db.scalar(select(func.count()).select_from(RetentionBatch))==0


def test_bounded_scheduled_progress_and_resume(database,automation):
    require_pg(database)
    result=work_once(database)
    assert result=={'status':'budget_exhausted','reason':None,'batches':2,'rows_processed':200}
    assert work_once(database)['status']=='not_due'
    with database.begin() as db:
        assert db.scalar(select(func.count()).select_from(Listing))==800
        state=db.get(RetentionAutomation,1);state.next_run_at=now()-timedelta(seconds=1)
        receipt=db.scalar(select(RetentionExecution));receipt.status='running';receipt.finished_at=None
    assert work_once(database)['rows_processed']==200
    with database() as db:
        assert db.get(RetentionExecution,1).status=='interrupted'
        assert db.scalar(select(func.sum(RetentionBatch.rows_removed)))==400


def test_policy_edit_invalidates_exact_automatic_scope(database,automation):
    with database() as db:
        update_policy(PolicyInput(raw_days=8),db.get(User,1),db)
    with database() as db:
        row=db.get(RetentionAutomation,1)
        assert not row.enabled and row.authorization is None and not approved_document(db,row)
    assert work_once(database)['status']=='inactive'


def test_scope_or_budget_tampering_invalidates_authorization(database,automation):
    with database.begin() as db:
        row=db.get(RetentionAutomation,1);doc=json.loads(row.authorization)
        doc['limits']['rows_per_batch']*=2;row.authorization=canonical(doc)
    assert work_once(database)['status']=='inactive'


def test_automatic_enable_requires_independent_approval(database,owner):
    assert owner.patch('/api/v1/admin/retention/automation',json={'enabled':True}).status_code==409
    assert owner.patch('/api/v1/admin/retention/automation',json={'enabled':False}).status_code==200


def test_backup_missing_preserves_all_rows(database,automation,monkeypatch):
    monkeypatch.setattr('market.retention_worker.recovery_ready',lambda _:False)
    result=work_once(database)
    assert result['status']=='paused' and result['batches']==0
    with database() as db: assert db.scalar(select(func.count()).select_from(Listing))==1000


def test_filesystem_and_wal_pressure_fail_closed(database,automation,monkeypatch):
    monkeypatch.setattr('market.capacity.filesystem',lambda:{'available_bytes':1,'reserve_bytes':2})
    assert 'filesystem' in work_once(database)['reason']


def test_failed_batch_rolls_back_and_receipt_survives(database,automation,monkeypatch):
    original=__import__('market.retention',fromlist=['execute_selected']).execute_selected
    def failed(*args):
        original(*args)
        raise RuntimeError('isolated injected crash')
    monkeypatch.setattr('market.retention.execute_selected',failed)
    assert work_once(database)['status']=='failed'
    with database() as db:
        assert db.scalar(select(func.count()).select_from(RetentionBatch))==0
        assert db.scalar(select(func.count()).select_from(Listing))==1000
        assert db.scalar(select(RetentionExecution.status))=='failed'


def test_collector_and_scheduler_single_writer(database,automation):
    with database.begin() as db:
        db.execute(text('SELECT pg_advisory_xact_lock(7140232)'))
        assert 'busy' in work_once(database)['reason']
    with database.begin() as db:
        db.execute(text('SELECT pg_advisory_xact_lock(7140238)'))
        assert work_once(database)['status']=='busy'


def test_collector_due_yields_budget(database,automation):
    with database.begin() as db:
        row=db.scalar(select(Market));row.enabled=True;row.next_check=now()
    assert 'Collector due' in work_once(database)['reason']


def test_missing_recovery_evidence_is_never_ready(tmp_path,monkeypatch):
    from market.retention_worker import recovery_ready
    monkeypatch.setenv('RETENTION_RECOVERY_EVIDENCE',str(tmp_path/'missing'))
    assert not recovery_ready(1)


def test_statement_timeout_rolls_back_and_next_run_can_retry(database,automation,monkeypatch):
    def slow(db,*args):db.execute(text('SELECT pg_sleep(4)'))
    monkeypatch.setattr('market.retention.execute_selected',slow)
    assert work_once(database)['status']=='failed'
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Listing))==1000
        assert db.scalar(select(RetentionExecution.rows_processed))==0


def test_wal_safety_pauses_before_deletion(database,automation,monkeypatch):
    from sqlalchemy.orm import Session
    original=Session.scalar
    def scalar(self,statement,*args,**kwargs):
        if 'pg_ls_waldir' in str(statement):return 3*1024**3
        return original(self,statement,*args,**kwargs)
    monkeypatch.setattr(Session,'scalar',scalar)
    result=work_once(database)
    assert result['status']=='paused' and 'WAL' in result['reason'] and result['rows_processed']==0


def test_scope_and_limits_require_exact_review_hash(database,automation):
    with database.begin() as db:
        with pytest.raises(ValueError,match='hash'):
            authorize_automatic(db,db.get(User,1),'fixture',limits=Limits(max_batches=3),expected_execution_hash=automation['execution_hash'])


def test_recovery_requires_present_rehashed_protected_local_and_off_vm(tmp_path,monkeypatch):
    from market.retention_worker import recovery_ready
    from market.db import now
    path=tmp_path/'evidence.json';monkeypatch.setenv('RETENTION_RECOVERY_EVIDENCE',str(path))
    stamp=now().isoformat();digest='a'*64
    data={'off_vm_verified_at':stamp,'off_vm_verified':True,'failure_domain':'synthetic-isolated-storage',
          'backup_id':'b'*32,'sha256':digest,'filename':'synthetic.dump','restored_archive_sha256':digest}
    manifest={'sha256':digest,'filename':'synthetic.dump','created_at':stamp,'restoration_verified_at':stamp,
              'protected':True,'required_by':['restore-recovery-gate'],'verification':'archive_integrity_verified','restored':{'fixture':True}}
    path.write_text(json.dumps(data));monkeypatch.setattr('market.backup_management.connect',lambda *args:manifest)
    assert recovery_ready(1)
    manifest['protected']=False
    assert not recovery_ready(1)
    manifest['protected']=True;data['off_vm_verified']=False;path.write_text(json.dumps(data))
    assert not recovery_ready(1)
    data['off_vm_verified']=True;data['off_vm_verified_at']=(now()-timedelta(days=2)).isoformat();path.write_text(json.dumps(data))
    assert not recovery_ready(1)


def test_off_vm_readiness_status_cannot_claim_missing_receipts(tmp_path,monkeypatch):
    from market.retention_worker import recovery_evidence_view
    monkeypatch.setenv('RETENTION_RECOVERY_EVIDENCE',str(tmp_path/'missing.json'))
    state=recovery_evidence_view()
    assert not state['off_vm_verification_recent'] and 'missing' in state['reason']


def test_restart_records_interruption_even_when_owner_paused(database,automation):
    with database.begin() as db:
        db.get(RetentionAutomation,1).enabled=False
        db.add(RetentionExecution(policy_hash=automation['policy_hash'],status='running'))
    assert work_once(database)['status']=='inactive'
    with database() as db: assert db.scalar(select(RetentionExecution.status))=='interrupted'


def test_empty_collector_yield_retries_without_phase_starvation(database,automation):
    at=now()
    with database.begin() as db:
        market=db.scalar(select(Market));market.enabled=True;market.next_check=at
    assert 'Collector due' in work_once(database,at=at)['reason']
    with database.begin() as db:
        assert at+timedelta(seconds=55)<db.get(RetentionAutomation,1).next_run_at<at+timedelta(seconds=65)
        db.scalar(select(Market)).enabled=False
    assert work_once(database,at=at+timedelta(seconds=30))['status']=='not_due'
    assert work_once(database,at=at+timedelta(seconds=61))['rows_processed']==200


def test_backup_validation_does_not_consume_deletion_work_budget(database,automation,monkeypatch):
    clock_value=[0]
    def verified(_):clock_value[0]=100;return True
    monkeypatch.setattr('market.retention_worker.recovery_ready',verified)
    assert work_once(database,clock=lambda:clock_value[0])['rows_processed']==200


def test_authorized_reserve_cannot_be_lowered_by_measurement_configuration(database,automation,monkeypatch):
    reserve=automation['scope']['minimum_filesystem_reserve_bytes']
    monkeypatch.setattr('market.capacity.filesystem',lambda:{'available_bytes':reserve-1,'reserve_bytes':1})
    assert 'filesystem' in work_once(database)['reason']


def test_changed_scheduler_source_invalidates_durable_authorization(database,automation,monkeypatch):
    from market.retention_worker import SCOPE
    monkeypatch.setitem(SCOPE,'scheduler_sha256','0'*64)
    assert work_once(database)['status']=='inactive'


@pytest.mark.parametrize('failure', [None, 'unprotected', 'missing_file', 'wrong_hash', 'not_restored', 'stale', 'future', 'wrong_approval', 'no_approval', 'invalid_mode'])
def test_explicit_local_only_exception_keeps_protected_restore_gates(tmp_path, monkeypatch, failure):
    from market.retention_worker import recovery_ready, recovery_evidence_view
    path = tmp_path/'local-receipt.json'
    approval = 'owner-request-2026-11-18-local-only'
    monkeypatch.setenv('RETENTION_RECOVERY_EVIDENCE', str(path))
    monkeypatch.setenv('RETENTION_RECOVERY_MODE', 'local_only')
    monkeypatch.setenv('RETENTION_LOCAL_RECOVERY_APPROVAL', approval)
    stamp = now().isoformat()
    digest = 'a'*64
    manifest = {'sha256':digest, 'filename':'synthetic.dump', 'created_at':stamp,
                'restoration_verified_at':stamp, 'protected':True, 'required_by':['restore-recovery-gate'],
                'verification':'archive_integrity_verified', 'restored':{'fixture':True}}
    evidence = {'backup_id':'b'*32, 'sha256':digest, 'filename':'synthetic.dump',
                'restored_archive_sha256':digest, 'local_restoration_verified_at':stamp,
                'owner_approval_reference':approval, 'off_vm_verified':False}
    if failure == 'unprotected': manifest['protected'] = False
    if failure == 'wrong_hash': manifest['sha256'] = 'c'*64
    if failure == 'not_restored': manifest['restored'] = None
    if failure in ('stale', 'future'):
        stamp = (now()+timedelta(days=-2 if failure=='stale' else 2)).isoformat()
        manifest.update(created_at=stamp, restoration_verified_at=stamp)
        evidence['local_restoration_verified_at'] = stamp
    if failure == 'wrong_approval': evidence['owner_approval_reference'] = 'another-request'
    if failure == 'no_approval': monkeypatch.delenv('RETENTION_LOCAL_RECOVERY_APPROVAL')
    if failure == 'invalid_mode': monkeypatch.setenv('RETENTION_RECOVERY_MODE', 'skip')
    path.write_text(json.dumps(evidence))
    def connect(*args):
        if failure == 'missing_file': raise HTTPException(409, 'missing or corrupt archive')
        return manifest
    monkeypatch.setattr('market.backup_management.connect', connect)
    assert recovery_ready(1) is (failure is None)
    state = recovery_evidence_view()
    assert state['off_vm_verification_recent'] is False
    if failure is None:
        assert state['required_evidence_recent'] is True
        assert state['off_vm_required'] is False
        # A local receipt cannot silently satisfy the unchanged default mode.
        monkeypatch.delenv('RETENTION_RECOVERY_MODE')
        assert recovery_ready(1) is False


def test_recovery_policy_change_invalidates_exact_execution_approval(database, automation, monkeypatch):
    from market.retention_worker import SCOPE
    monkeypatch.setitem(SCOPE, 'recovery_policy', {'mode':'local_only', 'valid':True,
        'off_vm_required':False, 'owner_approval_reference':'new-owner-exception'})
    assert work_once(database)['status'] == 'inactive'


def test_empty_raw_backlog_skips_retained_listing_heap(database, automation):
    from sqlalchemy import update
    from market.retention import candidates, policy_view
    from market.retention_worker import batch_selection
    require_pg(database)
    with database.begin() as db:
        db.execute(update(Observation).values(retrieved_at=now()))
        snapshot_id = db.scalar(select(Observation.snapshot_id).limit(1))
        db.execute(text('''INSERT INTO listings (snapshot_id,auction_id,item_id,variant,variant_key,quantity,buyout,unit_price)
            SELECT :snapshot_id,n,123,'{}','retained-variant',3,1001,333
            FROM generate_series(10000,110000) n'''), {'snapshot_id':snapshot_id})
        db.execute(text('ANALYZE listings'))
        db.execute(text('ANALYZE snapshots'))
        for name, model, predicate in candidates(db, policy_view(db), now()):
            if name != 'raw_listings': continue
            query = batch_selection(model, predicate, 5000)
            assert db.execute(query).all() == []
            sql = str(query.compile(db.bind, compile_kwargs={'literal_binds':True}))
            plan = db.execute(text('EXPLAIN (ANALYZE, FORMAT JSON) '+sql)).scalar()[0]['Plan']
            def listing_visits(node):
                own = ((node.get('Actual Rows',0)+node.get('Rows Removed by Filter',0))*node.get('Actual Loops',1)
                       if node.get('Relation Name') == 'listings' else 0)
                return own + sum(listing_visits(child) for child in node.get('Plans',[]))
            # Proving that no snapshot is eligible must not scan its retained heap.
            assert listing_visits(plan) < 100
        assert db.scalar(select(func.count()).select_from(Listing)) == 101001


def test_api_health_failure_pauses_before_source_deletion(database,automation,monkeypatch):
    require_pg(database)
    monkeypatch.setattr('market.maintenance_resources.health_reason',lambda:'Market API health check failed; cleanup paused')
    result=work_once(database)
    assert result['status']=='paused' and result['batches']==0
    with database() as db:assert db.scalar(select(func.count()).select_from(Listing))==1000


def test_database_pressure_pauses_before_source_deletion(database,automation,monkeypatch):
    require_pg(database)
    monkeypatch.setattr('market.maintenance_resources.database_reason',lambda db:'Database activity or lock waits exceed the cleanup safety threshold')
    result=work_once(database)
    assert result['status']=='paused' and result['batches']==0


def test_recovery_health_respects_archive_expiry_even_when_restore_is_recent(tmp_path,monkeypatch):
    from market.retention_worker import recovery_evidence_view
    path=tmp_path/'receipt.json'
    monkeypatch.setenv('RETENTION_RECOVERY_EVIDENCE',str(path))
    monkeypatch.setenv('RETENTION_RECOVERY_MODE','local_only')
    monkeypatch.setenv('RETENTION_LOCAL_RECOVERY_APPROVAL','fixture-approval')
    evidence=dict(local_restoration_verified_at=now().isoformat(),owner_approval_reference='fixture-approval',
                  expires_at=(now()-timedelta(seconds=1)).isoformat())
    path.write_text(json.dumps(evidence))
    assert recovery_evidence_view()['required_evidence_recent'] is False
    evidence['expires_at']=(now()+timedelta(hours=1)).isoformat();path.write_text(json.dumps(evidence))
    assert recovery_evidence_view()['required_evidence_recent'] is True


def test_cycle_leaves_transaction_headroom_instead_of_starting_near_deadline(database,automation):
    moments=iter([0,18.1])
    result=work_once(database,clock=lambda:next(moments))
    assert result['status']=='budget_exhausted' and result['batches']==0 and result['rows_processed']==0


def test_aggregation_integrity_failure_disables_cleanup_until_review(database,automation,monkeypatch):
    from market.retention_worker import state_view
    def mismatch(*args):raise HTTPException(409,'Synthetic aggregate mismatch')
    monkeypatch.setattr('market.compaction_safety.verify_statistics',mismatch)
    with database() as db:before=db.scalar(select(func.count()).select_from(Listing))
    result=work_once(database)
    assert result['status']=='paused' and result['rows_processed']==0
    with database() as db:
        assert db.get(RetentionAutomation,1).enabled is False
        assert db.scalar(select(func.count()).select_from(Listing))==before
        assert 'Synthetic aggregate mismatch' in state_view(db)['paused_reason']
