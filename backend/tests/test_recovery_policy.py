"""Deterministic item-centric policy and tracker checks. No real provider I/O."""
from datetime import timedelta
import json
from types import SimpleNamespace as Obj
import pytest
from sqlalchemy import select,func
from market.db import now
from market.recovery_policy import provider_action, gaps, choose
from market.metadata_recovery import ensure_providers, enqueue, tick, schedule_automatic
from market.models import ItemMetadata, ItemMedia, MetadataSource, MetadataProvider, MetadataAttempt, MetadataTask, Market
from market.metadata_catalog import store_source
from test_metadata_recovery import setup, tooltip, response


def provider(ident='foreverdb',**changes):
    return Obj(provider=ident,enabled=True,automatic=True,expires_at=None,last_error=None,**changes)


def source(**changes):
    values=dict(provider='foreverdb',status='available',fields_json='{"name":"Known"}',source_json='{"item_mapping_version":2,"item_build":"1.60.1.70532"}',checked_at=now()-timedelta(minutes=10),retry_at=now()+timedelta(hours=23),http_status=200,recovery_json='{"new_fields":[]}')
    values.update(changes)
    return Obj(**values)


def test_capabilities_do_not_use_name_card_for_quality():
    assert provider_action(provider('everloot'),None,['quality'],now())['reason']=='incapable'
    assert provider_action(provider('everloot'),None,['name'],now())['eligible']


def test_recently_unproductive_prefers_independent_source():
    at=now()
    f=provider_action(provider(),source(retry_at=at-timedelta(seconds=1)),['quality'],at)
    w=provider_action(provider('thewowdb'),None,['quality'],at)
    assert f['reason']=='recently_unproductive' and not f['eligible']
    assert choose([f,w],3)['provider']=='thewowdb'


@pytest.mark.parametrize('status,code,reason', [('missing',404,'negative_cache'),('available',304,'waiting_for_refresh'),('rate_limited',429,'temporarily_unavailable')])
def test_source_cache_cannot_be_forced_after_failure(status,code,reason):
    at=now()
    result=provider_action(provider(),source(status=status,http_status=code,recovery_json=None),['quality'],at,force=False)
    assert not result['eligible'] and result['reason']==reason
    if code!=304: assert not provider_action(provider(),source(status=status,http_status=code),['quality'],at,force=True)['eligible']


def test_disabled_expired_missing_and_cooldown():
    at=now();p=provider();p.enabled=False
    assert provider_action(p,None,['name'],at)['reason']=='provider_disabled'
    p.enabled=True
    assert provider_action(p,None,['name'],at,credentials=False)['reason']=='credential_unavailable'
    p.expires_at=at-timedelta(seconds=1)
    assert not provider_action(p,None,['name'],at)['eligible']
    p.expires_at=None
    r=provider_action(p,None,['name'],at,provider_due=at+timedelta(minutes=5))
    assert not r['eligible'] and r['reason']=='provider_cooldown'


def test_applicable_profile_does_not_require_equipment_for_cloth():
    row=Obj(catalog_json=json.dumps({'fields':{'name':'Cloth','class':'Trade Goods','quality':'COMMON'}}),details=None,name=None,fallback_name='Cloth',quality=None)
    assert gaps(row,None,{})=={'name':False,'icon':True,'essential':[],'details':False}
    row.catalog_json=json.dumps({'fields':{'name':'Sword','class':'Weapon','quality':'RARE'}})
    assert gaps(row,None,{})['essential']==['level','slot']
    src=source();assert not gaps(row,None,{'foreverdb':src})['details']


def test_local_artwork_does_not_repeat_metadata():
    src=source(source_json='{"icon_url":"https://foreverdb.net/icons/1.webp"}')
    assert provider_action(provider(),src,['artwork'],now())['reason']=='local_artwork_reference'


def test_tracker_is_admin_only_and_local(owner,database,monkeypatch):
    market=setup(database)
    def forbidden(*args,**kwargs): raise AssertionError('GET must not request providers')
    monkeypatch.setattr('market.metadata_providers.fetch',forbidden)
    summary=owner.get(f'/api/v1/admin/item-metadata/tracker?market_id={market}')
    assert summary.status_code==200,summary.text
    data=summary.json();assert data['summary']['observed']==2 and data['summary']['missing_names']==2
    assert len(data['rows'])==2 and all(r['missing'] for r in data['rows'])
    assert owner.get('/api/v1/admin/item-metadata/tracker/efficiency').status_code==200
    detail=owner.get(f'/api/v1/admin/item-metadata/tracker/720?market_id={market}')
    assert detail.status_code==200,detail.text
    assert detail.json()['attempts']==[]
    from market.models import User
    with database.begin() as db:db.get(User,1).role='member'
    assert owner.get(f'/api/v1/admin/item-metadata/tracker?market_id={market}').status_code==403
    with database.begin() as db:db.get(User,1).role='admin'
    owner.post('/api/v1/auth/logout')
    assert owner.get(f'/api/v1/admin/item-metadata/tracker?market_id={market}').status_code==401


def test_partial_recovery_rechecks_queued_goals(database):
    market=setup(database)
    with database.begin() as db:
        # Two independent jobs can coexist, but the second name-only endpoint
        # must be skipped once the first job commits its useful name.
        enqueue(db,market,'single',['everloot'],item_id=720,budget=1,actor_id=1)
        enqueue(db,market,'missing',['everloot'],limit=1,budget=1,actor_id=1)
    calls=[]
    def fetcher(*args,**kwargs): calls.append(args);return response(body=tooltip())
    tick(database,fetcher=fetcher,automatic=False)
    tick(database,at=now()+timedelta(hours=2),fetcher=fetcher,automatic=False)
    assert len(calls)==1
    with database() as db:
        assert db.scalar(select(func.count()).select_from(MetadataAttempt))==1
        a=db.scalar(select(MetadataAttempt));assert json.loads(a.new_json)==['name']
        assert db.scalar(select(MetadataTask).where(MetadataTask.state=='skipped')) is not None


def test_missing_names_precede_foreverdb_detail_upgrades(database):
    market=setup(database,provider='foreverdb');at=now()
    with database.begin() as db:
        for p in db.scalars(select(MetadataProvider)):p.enabled=p.automatic=p.provider=='foreverdb'
        db.get(MetadataProvider,'foreverdb').credential=b'synthetic-encrypted-placeholder'
        store_source(db,'us',720,'thewowdb',{'name':'Known equipment','quality':'RARE','class':'Weapon','slot':'Main Hand','level':20},{'provider':'thewowdb','edition':'forever','locale':'en_US'},at=at)
        schedule_automatic(db,at,allow_mock=True)
        task=db.scalar(select(MetadataTask))
        assert task.item_id==721
        assert json.loads(task.decision_json)['priority']==1


def test_icons_precede_essentials_with_capable_endpoint(database):
    market=setup(database,provider='foreverdb');at=now()
    with database.begin() as db:
        for p in db.scalars(select(MetadataProvider)):p.enabled=p.automatic=p.provider=='foreverdb'
        db.get(MetadataProvider,'foreverdb').credential=b'synthetic-placeholder'
        for ident in (720,721):store_source(db,'us',ident,'everloot',{'name':f'Synthetic {ident}'},{'provider':'everloot','edition':'forever','locale':'en_US'},at=at)
        schedule_automatic(db,at,allow_mock=True)
        task=db.scalar(select(MetadataTask))
        assert task.provider=='foreverdb' and json.loads(task.decision_json)['priority']==2


def test_untried_provider_not_hidden_by_other_negative_cache(database):
    market=setup(database,provider='thewowdb');at=now()
    with database.begin() as db:
        for p in db.scalars(select(MetadataProvider)):p.enabled=p.automatic=p.provider in ('thewowdb','blizzard')
        db.add(MetadataSource(region='us',item_id=720,provider='blizzard',status='metadata_unavailable',http_status=404,retry_at=at+timedelta(days=7),checked_at=at))
        schedule_automatic(db,at,allow_mock=True)
        task=db.scalar(select(MetadataTask))
        assert task.provider=='thewowdb' and task.item_id==720


def test_tracker_server_filters_sort_and_pagination(owner,database):
    market=setup(database);at=now()
    with database.begin() as db:
        store_source(db,'us',720,'everloot',{'name':'Synthetic Alpha'},{'provider':'everloot','edition':'forever','locale':'en_US'},at=at)
    root=f'/api/v1/admin/item-metadata/tracker?market_id={market}'
    data=owner.get(root+'&limit=1&sort=item_id&desc=true').json()
    assert data['total']==2 and data['rows'][0]['item_id']==721
    assert owner.get(root+'&limit=1&offset=1&sort=item_id&desc=true').json()['rows'][0]['item_id']==720
    assert owner.get(root+'&missing=name').json()['total']==1
    assert owner.get(root+'&q=Alpha').json()['rows'][0]['item_id']==720
    assert owner.get(root+'&sort=unsupported').status_code==422
    assert owner.get(root+'&limit=101').status_code==422
    assert owner.get(root+'&provider=everloot').json()['total']==1


def test_forward_efficiency_counts_once_and_keeps_unknown_reservations(owner,database):
    market=setup(database);at=now()
    with database.begin() as db:
        db.add_all([MetadataAttempt(provider='foreverdb',region='us',item_id=720,kind='metadata',started_at=at,state='finished',completed_at=at,http_status=200,outcome='name_recovered',new_json='["name","quality"]',returned_json='["name","quality"]'),
                    MetadataAttempt(provider='thewowdb',region='us',item_id=720,kind='metadata',started_at=at,state='finished',completed_at=at,http_status=304,outcome='already_known',new_json='[]',returned_json='[]'),
                    MetadataAttempt(provider='foreverdb',region='us',item_id=721,kind='metadata',started_at=at,state='reserved'),
                    MetadataAttempt(provider='foreverdb',region='us',item_id=720,kind='validation',started_at=at,state='finished',completed_at=at,http_status=200,outcome='validation_confirmed',new_json='[]',returned_json='[]')])
    response=owner.get('/api/v1/admin/item-metadata/tracker/efficiency?days=1')
    assert response.status_code==200,response.text
    data=response.json();assert data['metadata_requests']==2 and data['useful_requests']==1 and data['useful_rate']==.5
    assert sum(p['unknown_reservations'] for p in data['providers'])==1
    detail=owner.get(f'/api/v1/admin/item-metadata/tracker/720?market_id={market}').json()
    assert len(detail['attempts'])==3 and detail['historical']==[]


def test_image_refresh_failure_keeps_valid_bytes_and_local_url_skips_metadata(database):
    from market.item_media import resolve_media_once
    from test_item_profiles import Client,PNG
    market=setup(database);at=now()
    with database.begin() as db:
        # Make only one item media-eligible.
        db.add(ItemMedia(region='us',item_id=721,data=PNG,byte_count=len(PNG),retry_after=at+timedelta(days=30)))
        store_source(db,'us',720,'thewowdb',{'name':'Synthetic image'},{'provider':'thewowdb','edition':'forever','locale':'en_US','icon_url':'https://thewowdb.com/assets/icons/test.png','build':'1.60.1.70532'},at=at)
        db.get(MetadataProvider,'thewowdb').enabled=True;db.get(MetadataProvider,'thewowdb').automatic=True
    client=Client()
    assert resolve_media_once(database,client,at=at,image_fetch=lambda _: (PNG,'image/png'))
    assert client.calls==0
    with database() as db:
        assert db.get(ItemMedia,('us',720)).data==PNG
        assert db.scalar(select(MetadataAttempt)).outcome=='icon_recovered'
    assert resolve_media_once(database,Client(status=503),at=at+timedelta(days=31),image_fetch=lambda _:pytest.fail('failed metadata must not download'))
    with database() as db:
        row=db.get(ItemMedia,('us',720));assert row.data==PNG and row.status=='available'


def test_bounded_fairness_gives_refresh_a_turn(database):
    from market.models import MetadataRecoveryState
    market=setup(database,provider='foreverdb');at=now()
    with database.begin() as db:
        for p in db.scalars(select(MetadataProvider)):p.enabled=p.automatic=p.provider=='foreverdb'
        db.get(MetadataProvider,'foreverdb').credential=b'synthetic-placeholder'
        store_source(db,'us',720,'foreverdb',{'name':'Synthetic stable cloth','class':'Trade Goods','quality':'COMMON'},
            {'provider':'foreverdb','edition':'forever','locale':'en_US','item_mapping_version':2,'item_build':'1.60.1.70532'},at=at-timedelta(days=2))
        db.add(MetadataRecoveryState(id=1,turn=19))
        db.flush();schedule_automatic(db,at,allow_mock=True)
        task=db.scalar(select(MetadataTask))
        assert task.item_id==720 and json.loads(task.decision_json)['priority']==5


def test_two_markets_share_regional_goal_without_duplicate_requests(database):
    market=setup(database);at=now()
    with database.begin() as db:
        another=Market(region='us',ruleset_id=2,house_id=115,source_kind='auctions',label='Synthetic other house',enabled=False,verified=True)
        db.add(another);db.flush()
        enqueue(db,market,'single',['everloot'],item_id=720,actor_id=1,at=at)
        enqueue(db,another.id,'single',['everloot'],item_id=720,actor_id=1,at=at)
    calls=[]
    fetcher=lambda *args,**kwargs:(calls.append(args),response(body=tooltip()))[1]
    tick(database,at=at,fetcher=fetcher,automatic=False)
    tick(database,at=at+timedelta(hours=2),fetcher=fetcher,automatic=False)
    assert len(calls)==1
    with database() as db:
        assert db.scalar(select(func.count()).select_from(MetadataAttempt))==1
        assert db.scalar(select(func.count()).select_from(MetadataTask).where(MetadataTask.state=='skipped'))==1


def test_concurrent_workers_keep_one_forward_attempt(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    market=setup(database);at=now();sent=Event();finish=Event();calls=[]
    with database.begin() as db:enqueue(db,market,'single',['everloot'],item_id=720,actor_id=1,at=at)
    def fetcher(*args,**kwargs):calls.append(args);sent.set();assert finish.wait(5);return response(body=tooltip())
    with ThreadPoolExecutor(max_workers=2) as executor:
        first=executor.submit(tick,database,at=at,fetcher=fetcher,automatic=False)
        assert sent.wait(5)
        second=executor.submit(tick,database,at=at,fetcher=fetcher,automatic=False)
        assert second.result(timeout=5) is False
        finish.set();assert first.result(timeout=5)
    assert len(calls)==1
    with database() as db:assert db.scalar(select(func.count()).select_from(MetadataAttempt))==1


def test_retried_request_keeps_both_429_and_success_evidence(database):
    market=setup(database);at=now()
    with database.begin() as db:enqueue(db,market,'single',['everloot'],item_id=720,actor_id=1,budget=2,at=at)
    tick(database,at=at,fetcher=lambda *args,**kwargs:response(429,headers={'Retry-After':'180'}),automatic=False)
    tick(database,at=at+timedelta(seconds=181),fetcher=lambda *args,**kwargs:response(body=tooltip()),automatic=False)
    with database() as db:
        attempts=list(db.scalars(select(MetadataAttempt).order_by(MetadataAttempt.id)))
        assert [a.http_status for a in attempts]==[429,200]
        assert attempts[0].outcome=='rate_limited' and json.loads(attempts[1].new_json)==['name']


def test_thewowdb_does_not_claim_normalized_class_or_slot():
    for goal in ('class','slot','binding','subclass'):
        assert provider_action(provider('thewowdb'),None,[goal],now())['reason']=='incapable'


def test_changed_known_value_is_useful_not_already_known(database):
    market=setup(database);at=now()
    from test_metadata_recovery import parse_everloot
    with database.begin() as db:
        fields,origin=parse_everloot(tooltip(name='Synthetic old name'),720,at=at-timedelta(days=2))
        store_source(db,'us',720,'everloot',fields,origin,at=at-timedelta(days=2))
        enqueue(db,market,'single',['everloot'],item_id=720,actor_id=1,force_refresh=True,at=at)
    tick(database,at=at,fetcher=lambda *args,**kwargs:response(body=tooltip(name='Synthetic corrected name')),automatic=False)
    with database() as db:
        attempt=db.scalar(select(MetadataAttempt))
        assert attempt.outcome=='metadata_updated' and json.loads(attempt.updated_json)==['name']
        assert json.loads(attempt.new_json)==[]


def test_ineligible_decision_is_persisted_without_inventing_request(database):
    from market.models import MetadataRecoveryItem
    from market.recovery_planner import remember_decision,plan_item,provider_context
    market=setup(database);at=now()
    with database.begin() as db:
        for p in db.scalars(select(MetadataProvider)):p.enabled=False
        plan=plan_item(None,None,{},provider_context(db,at),at,automatic=True)
        remember_decision(db,('us',720),plan,at)
    with database() as db:
        row=db.get(MetadataRecoveryItem,('us',720,'en_US'))
        assert row.status=='no_eligible_provider' and row.next_at is None
        assert db.scalar(select(func.count()).select_from(MetadataAttempt))==0
        assert json.loads(row.decision_json)['chosen'] is None


def test_blizzard_cooldown_does_not_stall_other_cached_artwork(database):
    import time
    from market.item_media import resolve_media_once
    from test_item_profiles import Client,PNG
    market=setup(database);at=now()
    with database.begin() as db:
        p=db.get(MetadataProvider,'blizzard');p.cooldown_until=at+timedelta(hours=1)
        p=db.get(MetadataProvider,'thewowdb');p.enabled=p.automatic=True
        store_source(db,'us',721,'thewowdb',{'name':'Synthetic cached artwork'},
            {'provider':'thewowdb','edition':'forever','locale':'en_US','build':'1.60.1.70532','icon_url':'https://thewowdb.com/assets/icons/test.png'},at=at)
    client=Client();client.blocked_until=time.monotonic()+3600
    assert resolve_media_once(database,client,at=at,image_fetch=lambda _: (PNG,'image/png'))
    assert client.calls==0
    with database() as db:assert db.get(ItemMedia,('us',721)).data==PNG
