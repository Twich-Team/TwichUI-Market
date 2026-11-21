"""Batched sync values must equal the unchanged independent asking-v1 reference."""
from datetime import timedelta
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from market.db import now
from market.ingest import ingest
from market.models import Market, SnapshotStatistic
from market.sync_api import compact, compact_many
from market.sync_generation import signature


def fixture(db):
    market=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Synthetic batch equivalence')
    db.add(market);db.flush()
    # A completed UTC day keeps fixture samples valid even just after midnight.
    at=now().replace(hour=12,minute=0,second=0,microsecond=0)-timedelta(days=1)
    observations=[]
    for index,days in enumerate([61,60,14,2,0]):
        rows=[{'id':1,'item':{'id':1},'quantity':3,'buyout':100+index},
              {'id':2,'item':{'id':1,'bonus_lists':[42]},'quantity':2,'buyout':201+index},
              {'id':3,'item':{'id':2},'quantity':7,'bid':100}]
        if days:rows.append({'id':4,'item':{'id':3},'quantity':1,'buyout':999})
        observations.append(ingest(db,market.id,json.dumps({'auctions':rows}).encode(),request_key=f'batch-{index}',
            retrieved_at=at-timedelta(days=days),synthetic=days==2))
    # Non-winning late synthetic observation and same-timestamp winner tie.
    observations.append(ingest(db,market.id,json.dumps({'auctions':[{'id':1,'item':{'id':1},'quantity':1,'buyout':5}]}).encode(),
        request_key='late-earlier-day',retrieved_at=at-timedelta(hours=1),synthetic=True))
    observations.append(ingest(db,market.id,json.dumps({'auctions':rows}).encode(),request_key='same-time-new-id',retrieved_at=at,synthetic=False))
    keys=list(db.execute(select(SnapshotStatistic.item_id,SnapshotStatistic.variant_key).where(
        SnapshotStatistic.snapshot_id.in_([row.snapshot_id for row in observations])).distinct()))
    return observations,keys


def test_page_batch_matches_reference_for_variants_missing_items_bid_only_rounding_and_windows(database):
    with database.begin() as db:
        observations,keys=fixture(db)
        for observation in observations[:5]+observations[-1:]:
            generation=signature(db,observation,observation.id)
            assert compact_many(db,observation,keys,generation)=={
                tuple(key):compact(db,observation,*key,observation.id) for key in keys}
        assert compact_many(db,None,keys,None)=={tuple(key):None for key in keys}
        assert compact_many(db,observations[-1],[],signature(db,observations[-1],observations[-1].id))=={}
        with pytest.raises(ValueError):compact_many(db,observations[-1],[(1,'base')]*101,None)


def test_page_statistics_query_count_is_independent_of_number_of_keys(database):
    with database.begin() as db:
        observations,keys=fixture(db);head=observations[-1];generation=signature(db,head,head.id)
        count=0
        def query(*arguments):
            nonlocal count
            if arguments[2].lstrip().upper().startswith('SELECT'):count+=1
        event.listen(db.bind,'before_cursor_execute',query)
        try:values=compact_many(db,head,keys,generation)
        finally:event.remove(db.bind,'before_cursor_execute',query)
        assert len(values)==len(keys) and count==1


def test_batch_rejects_unsupported_historical_algorithm_even_for_missing_current_item(database):
    with database.begin() as db:
        observations,keys=fixture(db);head=observations[-1]
        old=db.scalar(select(SnapshotStatistic).where(SnapshotStatistic.snapshot_id==observations[1].snapshot_id,SnapshotStatistic.item_id==3))
        old.algorithm='unsupported-fixture';db.flush()
        with pytest.raises(HTTPException) as rejected:compact_many(db,head,keys,signature(db,head,head.id))
        assert rejected.value.status_code==409
        with pytest.raises(HTTPException):compact(db,head,old.item_id,old.variant_key,head.id)


def test_bounded_page_keys_match_independent_union_across_variants_and_deletions(database):
    from market.sync_api import page_keys
    with database.begin() as db:
        observations,_=fixture(db)
        # Independently compute the complete union once, then compare each cursor
        # boundary/limit. Mixed snapshots include missing and same-item variants.
        snapshots=[observations[0].snapshot_id,observations[-1].snapshot_id]
        all_keys=sorted(set(tuple(row) for row in db.execute(select(
            SnapshotStatistic.item_id,SnapshotStatistic.variant_key).where(
                SnapshotStatistic.snapshot_id.in_(snapshots)))))
        for ids in [snapshots,snapshots+snapshots,[],snapshots[:1]]:
            expected=all_keys if len(set(ids))==2 else sorted(set(tuple(row) for row in db.execute(select(
                SnapshotStatistic.item_id,SnapshotStatistic.variant_key).where(SnapshotStatistic.snapshot_id.in_(ids)))))
            for after in [(0,''),*expected,(2**31-1,'f'*64)]:
                for limit in [1,2,50,100]:
                    assert [tuple(row) for row in page_keys(db,ids,after,limit)]==[key for key in expected if key>after][:limit+1]
