from datetime import timedelta
from sqlalchemy import func, select, text
from market.db import now
from market.models import StorageMeasurement
from market.storage import history, sample


def test_hourly_sampling_is_idempotent_and_retention_is_bounded(database):
    at=now().replace(minute=0,second=0,microsecond=0)
    with database.begin() as db:
        db.add(StorageMeasurement(sampled_at=at-timedelta(days=91),database_bytes=100))
    assert sample(database,at=at)=='sampled'
    assert sample(database,at=at+timedelta(minutes=30))=='already_sampled'
    with database.begin() as db:
        rows=list(db.scalars(select(StorageMeasurement)))
        assert len(rows)==1 and rows[0].database_bytes>0
        assert history(db)['delta_bytes'] is None
    assert sample(database,at=at+timedelta(hours=1))=='sampled'
    with database.begin() as db:
        result=history(db)
        assert len(result['samples'])==2 and result['elapsed_seconds']==3600
        assert result['bytes_per_day']==result['delta_bytes']*24


def test_growth_reports_signed_observations_without_invented_history(owner,database):
    assert owner.get('/api/v1/admin/storage').json()['growth']['samples']==[]
    at=now().replace(minute=0,second=0,microsecond=0)
    with database.begin() as db:
        db.add_all([StorageMeasurement(sampled_at=at-timedelta(days=1),database_bytes=2000),
                    StorageMeasurement(sampled_at=at,database_bytes=1000)])
    growth=owner.get('/api/v1/admin/storage').json()['growth']
    assert growth['delta_bytes']==-1000 and growth['bytes_per_day']==-1000
    assert len(growth['samples'])==2


def test_competing_sampler_does_not_write(database):
    with database.begin() as db:
        db.execute(text('SELECT pg_advisory_xact_lock(7140234)'))
        assert sample(database)=='busy'
        assert db.scalar(select(func.count()).select_from(StorageMeasurement))==0
