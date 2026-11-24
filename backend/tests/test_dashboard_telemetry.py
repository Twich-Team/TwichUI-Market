"""Read-only dashboard accounting; disposable market_test or in-memory SQLite."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from market import backup_management
from market.db import now
from market.maintenance_health import activity, composition
from market.models import Market, RetentionBatch, Snapshot, StorageMeasurement
from market.storage import history


def test_activity_uses_snapshot_metadata_and_actual_committed_rows(database):
    at = now().replace(hour=12, minute=0, second=0, microsecond=0)
    yesterday = at-timedelta(days=1)
    with database.begin() as db:
        market = Market(region='us', ruleset_id=2, house_id=114,
                        source_kind='auctions', label='Dashboard fixture')
        db.add(market); db.flush()
        # No listing heap population is needed to read metadata. Retained
        # metadata includes snapshots whose original raw listings were pruned.
        db.add_all([Snapshot(market_id=market.id, content_hash=str(index)*64,
            created_at=stamp, listing_count=count, raw_retained=False)
            for index, stamp, count in [(1,yesterday,100),(2,yesterday,50),
                                       (3,at-timedelta(days=40),900)]])
        db.add_all([RetentionBatch(actor_id=1, policy_hash='a'*64, stage=stage,
            rows_removed=count, cutoff=yesterday, created_at=yesterday)
            for stage,count in [('raw_listings',30),('intraday_statistics',7)]])
    with database() as db:
        result=activity(db,at)
        assert result['unit']=='records' and len(result['days'])==1
        day=result['days'][0]
        assert day['raw_added']==150 and day['raw_removed']==30
        assert day['removed_by_category']['intraday_statistics']==7
        assert 'disk bytes are not measured' in result['notice']


def test_existing_storage_samples_keep_missing_observations_unknown(database):
    at=now()
    with database.begin() as db:
        db.add(StorageMeasurement(sampled_at=at,database_bytes=100,
            filesystem_available_bytes=None,retention_eligible_rows=None,
            retention_processed_rows=None))
    with database() as db:
        sample=history(db)['samples'][0]
        assert sample['database_bytes']==100
        assert sample['filesystem_available_bytes'] is None
        assert sample['retention_processed_rows'] is None


def test_composition_accounts_for_table_toast_indexes_and_remaining_files_once():
    rows=[dict(relname='listings',table_bytes=40,index_bytes=20),
          dict(relname='snapshot_statistics',table_bytes=10,index_bytes=5),
          dict(relname='users',table_bytes=5,index_bytes=1)]
    db=SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name='postgresql')),
                       execute=lambda _:SimpleNamespace(mappings=lambda:rows))
    result=composition(db,100)
    groups={row['key']:row['bytes'] for row in result['categories']}
    assert result['status']=='measured'
    assert groups['raw']==40 and groups['indexes']==26 and groups['other']==24
    assert sum(groups.values())==100
    assert composition(db,10)['status']=='changed_during_measurement'


def test_composition_on_unsupported_database_is_unavailable(database):
    with database() as db:
        if db.bind.dialect.name!='postgresql':
            result=composition(db,None)
            assert result['status']=='unavailable' and result['categories']==[]


def test_inventory_filters_are_validated_encoded_and_keep_default_compatibility(owner):
    with patch.object(backup_management,'connect',return_value={'items':[]}) as connect:
        response=owner.get('/api/v1/admin/backups',params={
            'search':'Market & NAS','protection':'protected','verification':'restored',
            'sort':'bytes_desc','backup_type':'manual','storage_id':'local'})
        assert response.status_code==200
        url=connect.call_args.args[1]
        assert 'search=Market+%26+NAS' in url and 'protection=protected' in url
        assert 'sort=bytes_desc' in url
        assert owner.get('/api/v1/admin/backups?sort=invalid').status_code==422
        assert owner.get('/api/v1/admin/backups?storage_id=../../secret').status_code==422


def test_new_telemetry_remains_administrator_only(client):
    assert client.get('/api/v1/admin/retention/health').status_code==401
    assert client.get('/api/v1/admin/storage').status_code==401
