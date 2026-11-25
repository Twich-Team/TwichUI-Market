"""Authenticated 2026-11-16 samples, plus explicitly synthetic failure mutations."""
from datetime import timedelta
import json
from pathlib import Path
import pytest
from sqlalchemy import select
from market.db import now
from market.foreverdb import item, related, needs_detail
from market.metadata_catalog import store_source, import_foreverdb_resource
from market.metadata_providers import IdentityMismatch
from market.metadata_recovery import enqueue, enqueue_related, ensure_providers, tick
from market.models import ItemMetadata, MetadataProvider, MetadataSource, MetadataTask, MetadataJob, MetadataResource, Market
from market.provider_secrets import encrypt

FIXTURES=Path(__file__).parent/'fixtures'/'foreverdb'
def body(name):return (FIXTURES/name).read_bytes()


def test_real_item_contract_and_exact_units():
    fields,origin=item(body('items-8188.json'),8188)
    assert fields['name']=='Explosive Shotgun' and fields['quality']=='UNCOMMON'
    assert fields['vendor_sell']=='6414' and fields['required_level']==32
    assert fields['weapon']=={'damage':{'min':'22','max':'42','school':'Physical'},'speed_seconds':'2.1'}
    assert fields['stats']==[{'stat_id':4,'label':'Strength','value':5}]
    assert fields['disenchant']['source']=='Classic data (CMaNGOS), not confirmed in Forever'
    assert origin['build']=='1.60.1.70938' and origin['resource_id']==8188
    assert origin['record']['icon']=='https://foreverdb.net/icons/135617.webp'
    fields,_=item(body('items-19019.json'),19019)
    assert fields['effects'][0]['spell_id']==21992 and '300 Nature damage' in fields['effects'][0]['text']
    fields,_=item(body('items-2589.json'),2589)
    assert fields['required_level']==0 and fields['disenchantable'] is False
    assert 'weapon' not in fields and 'disenchant' not in fields


@pytest.mark.parametrize('mutation',[
    {'id':8189},{'requiredLevel':True},{'sellPrice':1.1},{'stats':[{'statId':4,'stat':'Strength','value':None}]},
    {'quality':'invented'},{'speed':float('inf')},{'effects':[{'spellId':3,'triggerId':0,'trigger':'use','text':3}]},
])
def test_malformed_real_response_mutations_fail_closed(mutation):
    value=json.loads(body('items-8188.json'));value['data'].update(mutation)
    with pytest.raises(ValueError):item(json.dumps(value).encode(),8188)


def test_synthetic_old_build_and_beta_qualifiers_are_not_current_verification():
    value=json.loads(body('items-8188.json'));value['data'].update(dataFromBuild='1.60.1.70888',betaEvent=True,speculation=True,speculationReasons=['Synthetic uncertainty test'])
    fields,origin=item(json.dumps(value).encode(),8188)
    assert origin['build']=='1.60.1.70888' and origin['current_build']=='1.60.1.70938'
    assert origin['confidence']=='retained_earlier_build' and fields['availability']['betaEvent']
    value['meta']['build']='12.1.0.12345'
    with pytest.raises(ValueError):item(json.dumps(value).encode(),8188)


@pytest.mark.parametrize(('upstream_build', 'display_build'), [
    ('71037', '71037'),
    (71037, '71037'),
    (' 71037 ', '71037'),
    (' 1.60.1.71037 ', '1.60.1.71037'),
])
def test_retained_build_formats_preserve_earlier_provenance(upstream_build, display_build):
    value = json.loads(body('items-8188.json'))
    value['meta']['build'] = '1.60.1.71091'
    value['data']['dataFromBuild'] = upstream_build

    fields, origin = item(json.dumps(value).encode(), 8188)

    assert fields['availability']['dataFromBuild'] == display_build
    assert origin['qualifiers']['dataFromBuild'] == origin['build'] == display_build
    assert origin['item_build'] == origin['current_build'] == '1.60.1.71091'
    assert origin['confidence'] == 'retained_earlier_build'
    assert origin['record']['dataFromBuild'] == upstream_build


@pytest.mark.parametrize(('data', 'meta'), [
    ({'id': 8189}, {}),
    ({}, {'build': '71091'}),
    ({}, {'edition': 'retail'}),
    ({'dataFromBuild': '12.0.1.71037'}, {}),
    ({'dataFromBuild': True}, {}),
    ({'dataFromBuild': 71037.0}, {}),
    ({'dataFromBuild': '７１０３７'}, {}),
])
def test_retained_build_format_does_not_relax_item_or_edition_checks(data, meta):
    value = json.loads(body('items-8188.json'))
    value['data'].update({'dataFromBuild': '71037', **data})
    value['meta'].update({'build': '1.60.1.71091', **meta})

    with pytest.raises(IdentityMismatch):
        item(json.dumps(value).encode(), 8188)


def test_recovery_stores_short_retained_build_in_item_profile(database, owner):
    at = now()
    with database.begin() as db:
        market_id = setup_provider(db)
        enqueue(db, market_id, 'single', ['foreverdb'], item_id=8188, budget=1, at=at)
    value = json.loads(body('items-8188.json'))
    value['meta']['build'] = '1.60.1.71091'
    value['data']['dataFromBuild'] = '71037'

    assert tick(database, at=at, automatic=False, fetcher=lambda *args, **kwargs: (
        {'status': 200, 'headers': {}}, json.dumps(value).encode()))

    response = owner.get(f'/api/v1/markets/{market_id}/item-profiles/8188')
    assert response.status_code == 200
    profile = response.json()
    assert profile['attributes']['availability']['dataFromBuild'] == '71037'
    source = profile['catalog']['provenance']['name']
    assert source['confidence'] == 'retained_earlier_build'
    assert source['build'] == '71037'
    assert source['current_build'] == '1.60.1.71091'
    with database() as db:
        assert db.get(MetadataSource, ('us', 8188, 'en_US', 'foreverdb')).status == 'available'


def test_related_real_contracts_preserve_source_and_quantities():
    records,origin=related(body('professions-alchemy.json'),'professions/alchemy')
    assert set(records)=={765,3371,247755,2447,247754}
    recipe=records[765]['crafting'][0]['recipe']
    assert recipe['makes']['count']==1 and recipe['reagents'][0]['count']==1
    assert recipe['skill']['orangeSource']=='client'
    assert recipe['learnedFrom']['sources']['ways']==['auto']
    records,_=related(body('vendors-54.json'),'vendors/54')
    assert records[2488]['vendors'][0]['offer']['price']==536
    assert records[2488]['vendors'][0]['vendor']['seenInForever'] is True
    records,_=related(body('itemsets-1.json'),'itemsets/1')
    assert records[11729]['item_sets'][0]['set']['bonuses'][0]['pieces']==2
    with pytest.raises(ValueError):related(body('vendors-54.json'),'vendors/55')


def setup_provider(db):
    ensure_providers(db)
    row=db.get(MetadataProvider,'foreverdb');row.enabled=True;row.automatic=False
    row.credential_key_id,row.credential=encrypt('foreverdb','synthetic-fixture-key')
    row.validated_at=now()
    market=Market(region='us',ruleset_id=1,house_id=114,source_kind='auctions',label='Fixture',enabled=True)
    db.add(market);db.flush();return market.id


@pytest.fixture(autouse=True)
def test_keyring(monkeypatch,tmp_path):
    from base64 import b64encode
    p=tmp_path/'keyring.json';p.write_text(json.dumps({'active':'test','keys':{'test':b64encode(b'x'*32).decode()}}));p.chmod(0o600)
    monkeypatch.setenv('METADATA_KEYRING_FILE',str(p))


def test_full_lifecycle_upgrade_partial_refresh_and_api(database,owner):
    at=now()
    with database.begin() as db:
        market_id=setup_provider(db)
        fields,origin=item(body('items-8188.json'),8188,at=at-timedelta(hours=1))
        # Existing name-only parser output with an unexpired cache must upgrade.
        origin.pop('item_mapping_version');origin.pop('mapping_version')
        store_source(db,'us',8188,'foreverdb',{'name':fields['name']},origin,at=at)
        row=db.get(MetadataSource,('us',8188,'en_US','foreverdb'));assert needs_detail(row)
        job,_=enqueue(db,market_id,'single',['foreverdb'],item_id=8188,budget=2,at=at);job_id=job.id
    requests=[]
    def fetcher(provider,ident,**kw):
        requests.append(kw);return {'status':200,'headers':{}},body('items-8188.json')
    assert tick(database,at=at,fetcher=fetcher,automatic=False)
    assert requests[0]['etag'] is None
    response=owner.get(f'/api/v1/markets/{market_id}/item-profiles/8188').json()
    assert response['attributes']['stats'][0]['value']==5
    assert response['attributes']['vendor_sell']=='6414'
    assert response['catalog']['provenance']['stats']['provider']=='foreverdb'
    with database.begin() as db:
        row=db.get(MetadataSource,('us',8188,'en_US','foreverdb'));assert not needs_detail(row)
        before=json.loads(row.fields_json)
        # Partial same-provider record must preserve rich facts and their origin.
        store_source(db,'us',8188,'foreverdb',{'name':'Explosive Shotgun','stats':[],'vendor_sell':None},
            {'provider':'foreverdb','edition':'forever','locale':'en_US','build':'1.60.1.70938','payload_hash':'partial'},at=at+timedelta(days=2))
        assert json.loads(row.fields_json)==before
    database.kw['bind'].dispose() # New connections must observe committed metadata.
    assert owner.get(f'/api/v1/markets/{market_id}/item-profiles/8188').json()['attributes']['weapon']['speed_seconds']=='2.1'


def test_related_job_uses_shared_quota_and_persists_resources(database,owner):
    at=now()
    with database.begin() as db:
        market_id=setup_provider(db)
        job,_=enqueue_related(db,market_id,'professions/alchemy',actor_id=1,pages=1,at=at)
        job_id=job.id
    calls=[]
    def fetcher(provider,ident,**kw):
        calls.append(kw);return {'status':200,'headers':{}},body('professions-alchemy.json')
    assert tick(database,at=at,fetcher=fetcher,automatic=False)
    assert calls[0]['resource']=='professions/alchemy' and calls[0]['offset']==0
    with database() as db:
        assert db.get(MetadataProvider,'foreverdb').day_used==1
        assert db.get(MetadataJob,job_id).requests_used==1
        assert db.get(MetadataResource,('us','professions/alchemy',0)).fields_json
        assert json.loads(db.get(ItemMetadata,('us',765)).catalog_json)['fields']['crafting'][0]['recipe']['spellId']==1245250
        assert db.get(MetadataSource,('us',1,'en_US','foreverdb')) is None
    assert owner.get(f'/api/v1/markets/{market_id}/item-profiles/765').json()['attributes']['crafting']
    # Cache persists across a new request/job; no second outbound call.
    with database.begin() as db:enqueue_related(db,market_id,'professions/alchemy',actor_id=1,pages=1,at=at+timedelta(seconds=4))
    tick(database,at=at+timedelta(seconds=4),fetcher=fetcher,automatic=False)
    assert len(calls)==1


@pytest.mark.parametrize('status,expected',[(401,'authorization'),(402,'subscription_required'),(403,'forbidden'),(404,'metadata_unavailable'),(429,'rate_limited'),(503,'upstream_error')])
def test_related_failures_preserve_data_and_charge_quota(database,status,expected):
    at=now()
    with database.begin() as db:
        market_id=setup_provider(db)
        import_foreverdb_resource(db,'us','vendors/54',body('vendors-54.json'),at=at)
        job,_=enqueue_related(db,market_id,'vendors/54',pages=1,at=at);job_id=job.id
    tick(database,at=at,automatic=False,fetcher=lambda *a,**kw:({'status':status,'headers':{'Retry-After':'60'}},b''))
    with database() as db:
        task=db.scalar(select(MetadataTask).where(MetadataTask.job_id==job_id))
        assert json.loads(task.result_json)['status']==expected
        assert task.state==('completed' if status==404 else 'queued' if status in (429,503) else 'failed')
        assert db.get(MetadataProvider,'foreverdb').day_used==1
        assert json.loads(db.get(MetadataSource,('us',2488,'en_US','foreverdb')).fields_json)['vendors']


def test_related_requests_are_bounded_and_share_item_pacing(database):
    at=now()
    with database.begin() as db:
        market_id=setup_provider(db)
        job,_=enqueue_related(db,market_id,'professions/alchemy',pages=2,at=at)
        assert job.total==2 and job.request_budget==2
        tasks=list(db.scalars(select(MetadataTask).where(MetadataTask.job_id==job.id).order_by(MetadataTask.item_id)))
        assert [(t.resource,t.item_id) for t in tasks]==[('professions/alchemy',1),('professions/alchemy',21)]
        with pytest.raises(ValueError):enqueue_related(db,market_id,'https://invalid.example',pages=1)
        with pytest.raises(ValueError):enqueue_related(db,market_id,'vendors/54',pages=2)
    calls=[]
    def fetcher(provider,ident,**kw):
        calls.append(kw);return {'status':200,'headers':{}},body('professions-alchemy.json' if kw['offset']==0 else 'professions-alchemy-learning.json')
    tick(database,at=at,fetcher=fetcher,automatic=False)
    tick(database,at=at,fetcher=fetcher,automatic=False)
    assert len(calls)==1
    # New worker connections resume the exact persisted resource and page.
    tick(database,at=at+timedelta(seconds=4),fetcher=fetcher,automatic=False)
    assert len(calls)==2 and calls[1]['offset']==20
    with database() as db:assert db.get(MetadataProvider,'foreverdb').day_used==2


def test_changed_build_enrichment_preserves_old_field_provenance(database):
    with database.begin() as db:
        fields,origin=item(body('items-8188.json'),8188)
        origin['current_build']=origin['item_build']='1.60.1.70888'
        store_source(db,'us',8188,'foreverdb',fields,origin)
        src=db.get(MetadataSource,('us',8188,'en_US','foreverdb'))
        assert needs_detail(src,'1.60.1.70938')
        assert not needs_detail(src,'1.60.1.70888')
        before=json.loads(src.source_json)['field_sources']['stats']
        store_source(db,'us',8188,'foreverdb',{'name':'Explosive Shotgun'},
            {**origin,'current_build':'1.60.1.70938','payload_hash':'synthetic-partial-new-build'})
        assert json.loads(src.source_json)['field_sources']['stats']==before


def test_new_related_build_does_not_mark_old_item_details_current(database):
    with database.begin() as db:
        fields,origin=item(body('items-8188.json'),8188)
        origin['current_build']=origin['item_build']='1.60.1.70888'
        store_source(db,'us',8188,'foreverdb',fields,origin)
        # A newer related response has its own build; it cannot renew core facts.
        store_source(db,'us',8188,'foreverdb',{'vendors':[]},
            {'provider':'foreverdb','edition':'forever','locale':'en_US','current_build':'1.60.1.70938','build':'1.60.1.70938','payload_hash':'synthetic-related'})
        src=db.get(MetadataSource,('us',8188,'en_US','foreverdb'))
        assert json.loads(src.source_json)['item_build']=='1.60.1.70888'
        assert needs_detail(src,'1.60.1.70938')
