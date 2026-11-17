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
