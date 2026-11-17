"""Synthetic documented-contract fixtures, never live-provider evidence."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import pytest
from sqlalchemy import func, select, text
from market.db import now
from market.ingest import ingest
from market.metadata import store_metadata
from market.metadata_catalog import backfill_legacy, import_everloot_page, store_source
from market.metadata_providers import fetch, parse_everloot, parse_foreverdb
from market.metadata_recovery import enqueue, ensure_providers, tick
from market.models import ItemMetadata, Market, MetadataJob, MetadataProvider, MetadataSource, MetadataTask, MetadataVersion, SecurityEvent, User
from market.provider_secrets import SecretUnavailable, decrypt
from market.security import aware, hasher


def tooltip(item_id=720, name='Fixture Recovered Gloves'):
    return json.dumps({'ok':True,'type':'item','id':item_id,'title':name,'color':None,'icon':None,'lines':[],
        'partial':False,'url':f'https://everloot.app/item/{item_id}',
        'attribution':{'licence':'CC BY-SA 4.0','credit':'Data from Everloot, CC BY-SA 4.0','source':'https://everloot.app'},
        'gameData':{'build':'1.60.1.70532'}}).encode()


def page(ids=(720,721), next_page=None):
    return json.dumps({'items':[{'itemId':i,'class':{'name':'Armor'},'subclass':None,'slot':{'name':'Hands'},'quality':{'name':'Rare'}} for i in ids],
        'gameData':{'build':'1.60.1.70532','credit':'Game data © Blizzard Entertainment'}, 'offset':0,'limit':2,'total':4,'next':next_page}).encode()


def setup(database, provider='everloot'):
    with database.begin() as db:
        ensure_providers(db);db.get(MetadataProvider,provider).enabled=True
        market=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Synthetic recovery fixture',enabled=True,verified=True)
        db.add(market);db.flush()
        ingest(db,market.id,b'{"auctions":[{"id":1,"item":{"id":720},"quantity":3,"buyout":1200},{"id":2,"item":{"id":721},"quantity":1,"buyout":2500}]}',request_key='recovery-fixture',synthetic=True)
        return market.id


def response(status=200, body=None, headers=None):
    return {'status':status,'headers':headers or {}},body if body is not None else tooltip()


@pytest.fixture
def keyfile(tmp_path,monkeypatch):
    path=tmp_path/'keyring.json';path.write_text(json.dumps({'active':'one','keys':{'one':base64.b64encode(b'1'*32).decode()}}));path.chmod(0o600)
    monkeypatch.setenv('METADATA_KEYRING_FILE',str(path))
    return path


def test_precedence_versions_conflicts_and_field_provenance(database):
    setup(database);at=now()
    with database.begin() as db:
        fields,src=parse_everloot(tooltip(),720,at=at);store_source(db,'us',720,'everloot',fields,src,at=at)
        import_everloot_page(db,'us',page(),at=at)
        store_metadata(db,'us',720,b'{"id":720,"name":"Fixture Primary Gloves","level":28}',at=at,synthetic=True)
        row=db.get(ItemMetadata,('us',720));catalog=json.loads(row.catalog_json)
        assert catalog['fields']['name']=='Fixture Primary Gloves' and catalog['fields']['slot']=='Hands'
        assert catalog['provenance']['name']['provider']=='blizzard'
        assert catalog['provenance']['slot']['confidence']=='game_file_unconfirmed'
        assert any(c['field']=='name' and c['alternative']=='Fixture Recovered Gloves' for c in catalog['conflicts'])
        src=db.get(MetadataSource,('us',720,'en_US','everloot'))
        assert json.loads(src.source_json)['field_sources']['name']['confidence']=='player_consensus'
        assert db.scalar(select(func.count()).select_from(MetadataVersion))==4


def test_legacy_multiline_tooltips_backfill_without_blocking_worker(database):
    lines = [{'kind':'effect', 'text':'Use: Adds this toy to your Toy Box.\n\nSummon a fixture.\t(10 Min Cooldown)'}]
    with database.begin() as db:
        row=ItemMetadata(region='us',item_id=22728,name='Synthetic multiline toy',namespace='static-forever-us',details=json.dumps({'scope':'base_item','lines':lines}))
        db.add(row);db.flush()
        original=row.details
        assert backfill_legacy(db)==1
        assert row.details==original
        assert json.loads(row.catalog_json)['fields']['lines']==lines
        assert json.loads(db.get(MetadataSource,('us',22728,'en_US','blizzard')).fields_json)['lines']==lines
        assert json.loads(row.catalog_json)['conflicts']==[]
        assert backfill_legacy(db)==0


@pytest.mark.parametrize('unsafe',['<script>bad</script>','bad\x00control','bad\rcontrol'])
def test_multiline_tooltip_support_keeps_markup_and_other_controls_rejected(database,unsafe):
    with database.begin() as db:
        origin={'provider':'blizzard','edition':'forever','locale':'en_US'}
        with pytest.raises(ValueError):
            store_source(db,'us',720,'blizzard',{'lines':[{'kind':'effect','text':unsafe}]},origin)


@pytest.mark.parametrize('mutation',[{'id':721},{'type':'npc'},{'gameData':{'build':'12.1.5.70783'}},{'attribution':{'licence':'unknown'}},{'url':'https://evil.test/'},{'title':'<script>bad</script>'}])
def test_everloot_rejects_unverified_data(mutation):
    value=json.loads(tooltip());value.update(mutation)
    with pytest.raises(ValueError):parse_everloot(json.dumps(value).encode(),720)


def test_placeholder_null_fields_and_wrong_foreverdb_build():
    value=json.loads(tooltip(name='Item 720'));value['gameData']=None
    fields,src=parse_everloot(json.dumps(value).encode(),720)
    assert fields=={} and src['build'] is None
    with pytest.raises(ValueError):parse_foreverdb(b'{"data":{"id":720,"name":"X"},"meta":{"build":"1.15.9.70576"}}',720)


def test_bulk_atomic_duplicates_and_fixed_pagination(database):
    setup(database)
    with database.begin() as db:
        with pytest.raises(ValueError):import_everloot_page(db,'us',page((720,720)))
        assert db.scalar(select(func.count()).select_from(MetadataVersion))==0
        count,offset=import_everloot_page(db,'us',page(next_page='https://evil.test/steal'))
        assert count==2 and offset==2 and db.get(ItemMetadata,('us',720)).name is None
    calls=[]
    fetch('everloot',25,offset=2,credential='evl_fake',transport=lambda url,**kw:(calls.append((url,kw)),response())[1])
    assert calls[0][0]=='https://everloot.app/api/items?offset=2&limit=500'
    assert calls[0][1]['authorization']=='Bearer evl_fake' and 'evl_fake' not in calls[0][0]


def test_job_dedupe_search_profile_export_and_measurements(owner,database):
    market=setup(database);body={'market_id':market,'mode':'single','item_id':720,'providers':['everloot'],'request_budget':1}
    assert owner.post('/api/v1/admin/item-metadata/preview',json=body).json()['estimated_requests']==1
    result=owner.post('/api/v1/admin/item-metadata/jobs',json=body);assert result.status_code==202
    job=result.json()['job_id'];assert not owner.post('/api/v1/admin/item-metadata/jobs',json=body).json()['created']
    before=owner.get(f'/api/v1/markets/{market}/items').json()['items'][0]
    calls=[];assert tick(database,fetcher=lambda *a,**kw:(calls.append(a),response())[1],automatic=False) and len(calls)==1
    detail=owner.get(f'/api/v1/admin/item-metadata/jobs/{job}').json()
    assert detail['counts']=={'completed':1} and detail['state']=='completed'
    assert detail['results'][0]['result']['recovered_fields']==['name']
    row=owner.get(f'/api/v1/markets/{market}/items?q=Recovered').json()['items'][0]
    assert row['name']=='Fixture Recovered Gloves' and row['metadata_provider']=='everloot'
    assert row['variant_key']==before['variant_key']
    with database() as db:
        from market.pricing import values
        prices=values(db,market,720,row['variant_key'])
        assert prices['supply']==3 and prices['lowest_buyout']==400
    profile=owner.get(f'/api/v1/markets/{market}/item-profiles/720').json()
    assert profile['source']['provider']=='everloot' and profile['catalog']['edition']=='forever'
    assert owner.get(f'/api/v1/metadata/markets/{market}').json()['items'][0]['name']=='Fixture Recovered Gloves'
    coverage=owner.get('/api/v1/admin/item-metadata',params={'market_id':market}).json()
    assert coverage['observed']==2 and coverage['resolved_names']==1 and coverage['name_percent']==50


@pytest.mark.parametrize('status,category',[(401,'authorization'),(403,'forbidden'),(404,'metadata_unavailable'),(429,'rate_limited')])
def test_failures_preserve_names_and_correct_categories(database,status,category):
    market=setup(database);at=now()
    with database.begin() as db:
        fields,src=parse_everloot(tooltip(),720,at=at-timedelta(days=1));store_source(db,'us',720,'everloot',fields,src,at=at-timedelta(days=1))
        job,_=enqueue(db,market,'single',['everloot'],item_id=720,budget=3,at=at,force_refresh=True);job_id=job.id
    assert tick(database,at=at,fetcher=lambda *a,**kw:response(status,headers={'Retry-After':'7200'}),automatic=False)
    with database() as db:
        assert db.get(MetadataSource,('us',720,'en_US','everloot')).status==category
        assert db.get(ItemMetadata,('us',720)).fallback_name=='Fixture Recovered Gloves'
        if status in (401,403,429):assert aware(db.get(MetadataProvider,'everloot').cooldown_until)>=at+timedelta(hours=2)
        assert db.scalar(select(MetadataTask).where(MetadataTask.job_id==job_id)).state==('completed' if status==404 else ('queued' if status==429 else 'failed'))


def test_304_and_refresh_cache(database):
    market=setup(database);at=now()
    with database.begin() as db:
        fields,src=parse_everloot(tooltip(),720,at=at-timedelta(days=1));store_source(db,'us',720,'everloot',fields,src,at=at-timedelta(days=1),etag='"fixture"')
        enqueue(db,market,'stale',['everloot'],at=at)
    seen=[];tick(database,at=at,fetcher=lambda *a,**kw:(seen.append(kw['etag']),response(304,b''))[1],automatic=False)
    assert seen==['"fixture"']
    with database.begin() as db:enqueue(db,market,'single',['everloot'],item_id=720,at=at)
    tick(database,at=at,fetcher=lambda *a,**kw:pytest.fail('cache bypass'),automatic=False)
    with database() as db:assert db.scalar(select(MetadataTask).order_by(MetadataTask.id.desc()).limit(1)).state=='skipped'


def test_pause_resume_cancel_crash_recovery_and_budget(owner,database):
    market=setup(database);at=now();body={'market_id':market,'mode':'missing','providers':['everloot'],'request_budget':1}
    job=owner.post('/api/v1/admin/item-metadata/jobs',json=body).json()['job_id']
    assert owner.post(f'/api/v1/admin/item-metadata/jobs/{job}/pause').status_code==200
    assert not tick(database,at=at,fetcher=lambda *a,**kw:pytest.fail('paused'),automatic=False)
    assert owner.post(f'/api/v1/admin/item-metadata/jobs/{job}/resume').status_code==200
    with database.begin() as db:
        task=db.scalar(select(MetadataTask).where(MetadataTask.job_id==job).order_by(MetadataTask.id).limit(1))
        task.state='running';task.attempts=1;task.lease_token='crashed';task.lease_until=at-timedelta(seconds=1);db.get(MetadataJob,job).requests_used=1
    tick(database,at=at+timedelta(seconds=1),fetcher=lambda *a,**kw:pytest.fail('charged budget lost'),automatic=False)
    detail=owner.get(f'/api/v1/admin/item-metadata/jobs/{job}').json()
    assert detail['state']=='completed' and detail['counts']=={'skipped':2}
    job=owner.post('/api/v1/admin/item-metadata/jobs',json=body).json()['job_id']
    assert owner.post(f'/api/v1/admin/item-metadata/jobs/{job}/cancel').status_code==200
    assert owner.get(f'/api/v1/admin/item-metadata/jobs/{job}').json()['counts']=={'cancelled':2}


def test_credentials_staged_failed_replacement_expiry_and_rotation(owner,database,keyfile):
    setup(database);at=now();fake='evl_fake_secret_value'
    assert owner.post('/api/v1/admin/metadata-providers/everloot/credentials',json={'key':fake,'expires_at':(at+timedelta(days=10)).isoformat()}).status_code==202
    with database() as db:
        row=db.get(MetadataProvider,'everloot');assert fake.encode() not in row.pending_credential and row.credential is None
    tick(database,at=at,fetcher=lambda *a,**kw:response(body=page()),automatic=False)
    with database() as db:
        row=db.get(MetadataProvider,'everloot');old=row.credential;assert decrypt('everloot',row.credential_key_id,row.credential)==fake
    assert owner.post('/api/v1/admin/metadata-providers/everloot/credentials',json={'key':'evl_replacement_rejected'}).status_code==202
    tick(database,at=at+timedelta(minutes=4),fetcher=lambda *a,**kw:response(401),automatic=False)
    with database() as db:
        row=db.get(MetadataProvider,'everloot');assert row.credential==old and row.pending_credential is None and row.validation_error=='authorization'
        assert all(fake not in event.detail for event in db.scalars(select(SecurityEvent)))
    status=owner.get('/api/v1/admin/metadata-providers');assert fake not in status.text and 'evl_replacement' not in status.text
    state=next(p for p in status.json()['providers'] if p['provider']=='everloot');assert state['expiration_warning']=='expires_within_14_days' and state['configured']
    keys=json.loads(keyfile.read_text());keys['keys']['two']=base64.b64encode(b'2'*32).decode();keys['active']='two';keyfile.write_text(json.dumps(keys))
    assert owner.post('/api/v1/admin/metadata-providers/rotate-encryption').json()['rotated_envelopes']==1
    with database() as db:
        row=db.get(MetadataProvider,'everloot');assert row.credential_key_id=='two' and decrypt('everloot','two',row.credential)==fake
        with pytest.raises(SecretUnavailable):decrypt('foreverdb','two',row.credential)


def test_secret_permissions_redaction_and_csrf(owner,database,keyfile):
    keyfile.chmod(0o644)
    assert owner.post('/api/v1/admin/metadata-providers/everloot/credentials',json={'key':'evl_fake_secret_value'}).status_code==503
    bad=owner.post('/api/v1/admin/metadata-providers/everloot/credentials',json=[{'key':'evl_do_not_echo'}])
    assert bad.status_code==422 and 'evl_do_not_echo' not in bad.text
    owner.headers.pop('x-csrf-token')
    assert owner.post('/api/v1/admin/metadata-providers/everloot/credentials',json={'key':'evl_fake_secret_value'}).status_code==403


def test_member_and_device_cannot_admin(client,database):
    with database.begin() as db:db.add(User(username='member',password_hash=hasher.hash('member password 12345'),role='member'))
    login=client.post('/api/v1/auth/login',json={'username':'member','password':'member password 12345'}).json();client.headers['x-csrf-token']=login['csrf_token']
    assert client.get('/api/v1/admin/metadata-providers').status_code==403
    assert client.post('/api/v1/admin/item-metadata/jobs',json={}).status_code==403
    token=client.post('/api/v1/devices',json={'name':'fixture'}).json()['token']
    assert client.get('/api/v1/admin/item-metadata',headers={'Authorization':'Bearer '+token}).status_code==403


def test_concurrent_dedupe_and_independent_collector_lock(database):
    market=setup(database)
    def queue():
        with database.begin() as db:return enqueue(db,market,'single',['everloot'],item_id=720)[0].id
    with ThreadPoolExecutor(max_workers=2) as pool:assert len(set(pool.map(lambda _:queue(),range(2))))==1
    with database.begin() as collector:
        collector.execute(text('SELECT pg_advisory_xact_lock(7140232)'))
        assert tick(database,fetcher=lambda *a,**kw:response(),automatic=False)


@pytest.mark.parametrize('days,warning',[(29,'expires_within_30_days'),(13,'expires_within_14_days'),(6,'expires_within_7_days'),(-1,'expired')])
def test_expiration_thresholds(owner,database,days,warning):
    setup(database)
    with database.begin() as db:db.get(MetadataProvider,'everloot').expires_at=now()+timedelta(days=days)
    state=next(p for p in owner.get('/api/v1/admin/metadata-providers').json()['providers'] if p['provider']=='everloot')
    assert state['expiration_warning']==warning


def test_malformed_refresh_and_timeout_retries_are_bounded(database):
    market=setup(database);at=now()
    with database.begin() as db:
        fields,src=parse_everloot(tooltip(),720);store_source(db,'us',720,'everloot',fields,src,at=at-timedelta(days=1))
        job,_=enqueue(db,market,'single',['everloot'],item_id=720,budget=3,at=at,force_refresh=True);job_id=job.id
    calls=[]
    def timeout(*a,**kw):calls.append(1);raise TimeoutError('fake secret must not be logged')
    for attempt in range(4):tick(database,at=at+timedelta(hours=attempt),fetcher=timeout,automatic=False)
    assert len(calls)==3
    with database() as db:
        task=db.scalar(select(MetadataTask).where(MetadataTask.job_id==job_id))
        assert task.state=='failed' and 'fake secret' not in task.result_json
        assert db.get(ItemMetadata,('us',720)).fallback_name=='Fixture Recovered Gloves'
    with database.begin() as db:enqueue(db,market,'single',['everloot'],item_id=720,at=at+timedelta(days=1))
    tick(database,at=at+timedelta(days=1),fetcher=lambda *a,**kw:response(body=b'{"id":999,"name":"wrong"}'),automatic=False)
    with database() as db:assert db.get(ItemMetadata,('us',720)).fallback_name=='Fixture Recovered Gloves'


def test_persistent_provider_hourly_budget_and_automatic_priority(database):
    market=setup(database);at=now()
    with database.begin() as db:
        blizzard=db.get(MetadataProvider,'blizzard');blizzard.automatic=False
        provider=db.get(MetadataProvider,'everloot');provider.automatic=True;provider.hourly_budget=1
        db.add(ItemMetadata(region='us',item_id=721,namespace='static-forever-us',requested_at=at))
    calls=[]
    def record(provider,item_id,**kw):calls.append(item_id);return response(body=tooltip(item_id))
    tick(database,at=at,fetcher=record)
    assert calls==[721]
    tick(database,at=at+timedelta(minutes=4),fetcher=record)
    assert calls==[721]
    # Minute accounting conservatively retains an intersecting bucket for <60s.
    tick(database,at=at+timedelta(hours=1,seconds=61),fetcher=record)
    assert calls==[721,720]


def test_bulk_job_imports_incrementally_and_stops_at_page_budget(database):
    market=setup(database);at=now()
    with database.begin() as db:job,_=enqueue(db,market,'bulk',['everloot'],budget=1,at=at);ident=job.id
    tick(database,at=at,fetcher=lambda *a,**kw:response(body=page(next_page='https://everloot.app/api/items?offset=2')),automatic=False)
    with database() as db:
        job=db.get(MetadataJob,ident)
        assert job.state=='completed' and job.requests_used==1 and job.total==1
        assert db.get(ItemMetadata,('us',720)).fallback_name is None
        assert json.loads(db.get(ItemMetadata,('us',720)).catalog_json)['fields']['quality']=='RARE'


def test_retry_after_dates_can_exceed_one_day():
    from email.utils import format_datetime
    from market.metadata_recovery import cooldown
    at=now();row=MetadataProvider(provider='everloot')
    cooldown(row,429,{'Retry-After':format_datetime(at+timedelta(days=3))},at)
    assert aware(row.cooldown_until)>=at+timedelta(days=3,seconds=-1)


def test_enrichment_without_oauth_does_not_create_automatic_blizzard_jobs(database,monkeypatch):
    setup(database)
    monkeypatch.delenv('BLIZZARD_CLIENT_ID',raising=False);monkeypatch.delenv('BLIZZARD_CLIENT_SECRET',raising=False)
    tick(database)
    with database() as db:assert db.scalar(select(func.count()).select_from(MetadataJob))==0


def test_artwork_and_name_work_share_budget_without_starvation(database,monkeypatch):
    import market.metadata_recovery as recovery
    import market.item_media as media
    from market.enrichment import tick as enrich
    from test_item_profiles import PNG
    setup(database,provider='blizzard');at=now()+timedelta(seconds=1)
    monkeypatch.setenv('BLIZZARD_CLIENT_ID','fixture');monkeypatch.setenv('BLIZZARD_CLIENT_SECRET','fixture')
    monkeypatch.setattr(recovery,'now',lambda:at);monkeypatch.setattr(media,'now',lambda:at)
    original=media.resolve_media_once
    monkeypatch.setattr(media,'resolve_media_once',lambda *a,**kw:original(*a,**kw,image_fetch=lambda _: (PNG,'image/png')))
    class Client:
        def fetch_item(self,region,item):return response(body=json.dumps({'id':item,'name':'Synthetic primary name'}).encode())
        def fetch_item_media(self,region,item):return response(body=json.dumps({'id':item,'assets':[{'key':'icon','value':'https://render.worldofwarcraft.com/us/icons/56/a.png'}]}).encode())
    result=enrich(database,Client());assert result['recovery'] and not result['media']
    at+=timedelta(seconds=16)
    result=enrich(database,Client());assert result['media']
    with database() as db:assert db.get(MetadataProvider,'blizzard').hour_used==2


def test_cooling_automatic_provider_does_not_block_another(database):
    market=setup(database);at=now()
    with database.begin() as db:
        db.get(MetadataProvider,'blizzard').automatic=False
        first=db.get(MetadataProvider,'everloot');first.automatic=True;first.hourly_budget=1
        first.hour_start=at;first.hour_used=1
        other=db.get(MetadataProvider,'thewowdb');other.enabled=other.automatic=True
    calls=[]
    # First provider gets a durable budget-waiting job, then the next provider gets a turn.
    tick(database,at=at,fetcher=lambda p,*a,**kw:(calls.append(p),response(403))[1])
    tick(database,at=at+timedelta(seconds=1),fetcher=lambda p,*a,**kw:(calls.append(p),response(403))[1])
    assert calls==['thewowdb']


def test_bulk_ignored_offset_cannot_claim_a_successful_import(database):
    market=setup(database);at=now()
    with database.begin() as db:job,_=enqueue(db,market,'bulk',['everloot'],budget=2,at=at);ident=job.id
    tick(database,at=at,fetcher=lambda *a,**kw:response(body=page(next_page='https://everloot.app/api/items?offset=2')),automatic=False)
    tick(database,at=at+timedelta(minutes=4),fetcher=lambda *a,**kw:response(body=page()),automatic=False)
    with database() as db:
        task=db.scalar(select(MetadataTask).where(MetadataTask.job_id==ident).order_by(MetadataTask.id.desc()).limit(1))
        assert task.state=='failed' and json.loads(task.result_json)['recovered_fields']==[]


@pytest.mark.parametrize('provider',['blizzard','thewowdb'])
def test_every_provider_connection_test_is_queued_and_validated(owner,database,provider):
    setup(database,provider=provider)
    assert owner.post(f'/api/v1/admin/metadata-providers/{provider}/test').status_code==202
    if provider=='blizzard':body=b'{"id":25,"name":"Fixture Sword"}'
    else:
        from test_community_metadata import payload
        value=payload();value['id']=25;body=json.dumps(value).encode()
    tick(database,fetcher=lambda *a,**kw:response(body=body),automatic=False)
    with database() as db:
        row=db.get(MetadataProvider,provider)
        assert row.validated_at is not None and not row.validation_requested and row.validation_error is None


def test_validated_keys_allow_bounded_higher_budgets_but_keyless_does_not(owner,database,keyfile):
    from market.metadata_recovery import reserve_budget
    from market.provider_secrets import encrypt
    setup(database);body={'enabled':True,'automatic':False,'hourly_budget':240,'daily_budget':2000}
    assert owner.patch('/api/v1/admin/metadata-providers/everloot',json=body).status_code==422
    with database.begin() as db:
        row=db.get(MetadataProvider,'everloot');row.credential_key_id,row.credential=encrypt('everloot','evl_fake_validated');row.validated_at=now()
    assert owner.patch('/api/v1/admin/metadata-providers/everloot',json=body).status_code==200
    with database.begin() as db:
        row=db.get(MetadataProvider,'everloot');at=now()
        assert reserve_budget(row,at) is None and aware(row.next_request_at)==at+timedelta(seconds=15)
        row.credential=None;row.next_request_at=None;row.hour_used=20
        assert reserve_budget(row,at)==aware(row.hour_start)+timedelta(hours=1)


def test_missing_batch_includes_named_items_without_basic_attributes(database):
    from market.metadata_recovery import candidates
    market=setup(database)
    with database.begin() as db:
        fields,origin=parse_everloot(tooltip(),720)
        store_source(db,'us',720,'everloot',fields,origin)
        assert 720 in [r[1] for r in candidates(db,market,'missing',100,['everloot'])]
        import_everloot_page(db,'us',page())
        assert [r[1] for r in candidates(db,market,'missing',100,['everloot'])]==[721]


def test_dashboard_pending_does_not_subtract_preserved_names_twice(owner,database):
    market=setup(database)
    with database.begin() as db:
        for item in (720,721):
            row=store_metadata(db,'us',item,json.dumps({'id':item,'name':'Synthetic cached name'}).encode(),synthetic=True)
            row.http_status=404;row.status='missing'
    stats=owner.get('/api/v1/admin/item-metadata',params={'market_id':market}).json()
    assert stats['primary_names']==2 and stats['primary_missing_responses']==2 and stats['primary_pending']==0


def test_foreverdb_coverage_and_verification_are_local_evidence(database, owner):
    from market.metadata_catalog import store_source
    from market.metadata_recovery import ensure_providers
    with database.begin() as db:
        ensure_providers(db)
        market = Market(region='us', ruleset_id=1, house_id=114, source_kind='auctions', label='Test', enabled=True)
        db.add(market);db.flush()
        market_id = market.id
        origin = {'provider':'foreverdb','edition':'forever','locale':'en_US','build':'1.60.1.70938',
            'confidence':'client_record_unverified','payload_hash':'test','retrieved_at':now().isoformat()}
        store_source(db,'us',25,'foreverdb',{'name':'Name only'},origin)
        store_source(db,'us',26,'foreverdb',{'name':'Detailed','quality':'RARE','level':0},origin)
    # Isolate the observation selector; persisted provider/source records and HTTP
    # serialization remain real. No auction observations or live calls are invented.
    from unittest.mock import patch
    from sqlalchemy import literal, union_all
    ids = union_all(select(literal('us').label('region'),literal(25).label('item_id')),
                    select(literal('us').label('region'),literal(26).label('item_id')))
    with patch('market.metadata_admin.observed_query',return_value=ids):
        overview = owner.get(f'/api/v1/admin/item-metadata?market_id={market_id}')
    assert overview.status_code == 200
    source = next(r for r in overview.json()['provider_records'] if r['provider']=='foreverdb')
    assert source['name_only']==1 and source['detailed_records']==1
    assert source['fields_available']['quality']==1 and source['fields_available']['level']==1
    assert source['builds']==[{'build':'1.60.1.70938','records':2}]
    provider = next(r for r in owner.get('/api/v1/admin/metadata-providers').json()['providers'] if r['provider']=='foreverdb')
    assert provider['website_verification']['status']=='unknown'
    assert provider['key_scope']=='unknown'
