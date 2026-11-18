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
