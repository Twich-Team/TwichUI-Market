"""Coverage is a set of regional base IDs, never sums of source/variant records."""
import json
from sqlalchemy import select
from market.db import now
from market.ingest import ingest
from market.metadata import store_metadata
from market.metadata_catalog import store_source
from market.metadata_recovery import enqueue
from market.models import Market, MetadataSource, ItemMetadata, ItemMedia


def test_coverage_denominators_unknown_errors_sources_and_overlap(owner,database):
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Synthetic coverage')
        db.add(market);db.flush();market_id=market.id
        rows=[{'id':i,'item':{'id':i},'quantity':1,'buyout':100} for i in range(1,9)]
        rows.append({'id':9,'item':{'id':1,'bonus_lists':[1]},'quantity':1,'buyout':100})
        ingest(db,market_id,json.dumps({'auctions':rows}).encode(),request_key='coverage',synthetic=True)
        store_metadata(db,'us',1,b'{"id":1,"name":"Primary"}',synthetic=True)
        origin={'provider':'everloot','edition':'forever','locale':'en_US','build':'1.60.1.fixture','confidence':'synthetic','payload_hash':'fixture','retrieved_at':now().isoformat()}
        store_source(db,'us',1,'everloot',{'name':'Alternate','quality':'UNCOMMON','level':0},origin)
        store_source(db,'us',2,'foreverdb',{'name':'Supplemental'},{**origin,'provider':'foreverdb'})
        db.add(ItemMetadata(region='us',item_id=4,namespace='static-forever-us',status='missing',http_status=404))
        db.add(MetadataSource(region='us',item_id=5,provider='everloot',http_status=403,status='forbidden'))
        db.add(MetadataSource(region='us',item_id=6,provider='everloot',http_status=200,status='available',fields_json='{}'))
        db.add(ItemMetadata(region='us',item_id=7,namespace='static-forever-us',status='error',http_status=429))
        db.add(ItemMedia(region='us',item_id=1,asset_hash='a'*64,data=b'x',byte_count=1))
        db.add(ItemMedia(region='us',item_id=2,asset_hash='b'*64))
        enqueue(db,market_id,'single',['everloot'],item_id=3,actor_id=1,budget=1)
        # Other-locale retained data cannot double-count the site's en_US coverage.
        db.add(MetadataSource(region='us',item_id=1,provider='everloot',locale='de_DE',http_status=200,status='available',fields_json='{"name":"Andere"}'))
    response=owner.get(f'/api/v1/admin/item-metadata?market_id={market_id}')
    assert response.status_code==200,response.text
    data=response.json()
    assert data['observed']==8 and data['resolved_names']==2 and data['missing_names']==6
    assert data['attributes_available']==1 and data['icons_available']==1 and data['icons_missing']==7
    assert data['name_percent']==25 and data['scoped_pending_items']==1
    assert (data['unknown_not_tried'],data['tried_unavailable'],data['failed_or_blocked'],data['checked_unresolved'])==(2,1,2,1)
    assert data['provider_name_overlap']==1 and data['conflicting_names']==1
    everloot=next(r for r in data['provider_records'] if r['provider']=='everloot')
    assert everloot['names_available']==1 and everloot['overlapping_names']==1 and everloot['conflicting_names']==1
    assert everloot['fields_available']['level']==1
    # A failed primary refresh does not turn a retained name into missing metadata.
    with database.begin() as db:
        row=db.get(ItemMetadata,('us',1));row.http_status=403;row.status='error'
    after=owner.get(f'/api/v1/admin/item-metadata?market_id={market_id}').json()
    assert after['resolved_names']==2 and after['failed_or_blocked']==2


def test_empty_coverage_reports_no_percent_and_no_invented_history(owner):
    data=owner.get('/api/v1/admin/item-metadata').json()
    assert data['observed']==0 and data['name_percent'] is None and data['attributes_available']==0
    assert data['unknown_not_tried']==data['failed_or_blocked']==0

    assert len(data['provider_records']) == 4
    assert all(all(count==0 for count in record['fields_available'].values()) for record in data['provider_records'])
