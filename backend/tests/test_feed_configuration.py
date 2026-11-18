"""Fresh source proof and owner/admin guard; entirely synthetic transport."""
import hashlib
import json
from urllib.parse import urlparse
import pytest
from sqlalchemy import func, select
from market.db import now
from market.feed_configuration import configure
from market.ingest import ingest
from market.models import Market, MarketFeed, Observation, SecurityEvent, User
from test_market_configuration import verified_player_mapping


def legacy(factory, *, mapped=True):
    with factory.begin() as db:
        if mapped: verified_player_mapping(db, 114, 'Horde')
        db.add(Market(id=2,region='us',ruleset_id=2,house_id=114,source_kind='auctions',
            label='Existing market fixture',enabled=True,verified=True,interval_seconds=300,next_check=now()))
        db.flush()
        ingest(db,2,b'{"auctions":[{"id":1,"item":{"id":25},"quantity":2,"buyout":999}]}',
            request_key='original-observation',synthetic=True)


class Source:
    def __init__(self, wrong_house=False):
        self.calls=[]
        self.wrong_house=wrong_house

    def authenticate(self): return 'synthetic-not-a-real-token'

    def throttle(self, metadata): pass

    def transport(self, url, **kwargs):
        self.calls.append(url)
        path=urlparse(url).path
        if path.endswith('/index'): body={'rulesets':[{'id':2}]}
        elif path.endswith('/auctions/'): body={'auctions':[{'id':114,'name':'Horde Auction House'}]}
        elif path.endswith('/114'):
            body={'id':114,'name':'Horde Auction House','auctions':[{'id':1,'item':{'id':25},'quantity':2,'buyout':999}]}
        else:
            house=113 if self.wrong_house else 114
            body={'_links':{'self':{'href':f'https://us.api.blizzard.com/data/wow/ruleset/2/auctions/{house}/commodities?namespace=dynamic-forever-us'}},
                'auctions':[{'id':2,'item':{'id':4306},'quantity':20,'unit_price':123}]}
        raw=json.dumps(body).encode()
        return {'url':url,'status':200,'headers':{'Battlenet-Namespace':'dynamic-forever-us'},
            'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)},raw

    def fetch(self, market):
        assert (market.region,market.ruleset_id,market.house_id,market.source_kind)==('us',2,114,'commodities')
        return self.transport('https://us.api.blizzard.com/data/wow/ruleset/2/auctions/114/commodities?namespace=dynamic-forever-us')


def test_dry_run_proves_both_feeds_without_activation_or_observations(database):
    legacy(database)
    source=Source()
    result=configure(1,factory=database,client=source,pause=lambda _:None)
    assert result['status']=='verified_dry_run' and len(source.calls)==4
    with database() as db:
        assert not db.get(Market,2).unified_coverage
        assert db.scalar(select(func.count()).select_from(MarketFeed))==0
        assert db.scalar(select(func.count()).select_from(Observation))==1


def test_activation_preserves_identity_history_cadence_and_is_idempotent(database):
    legacy(database)
    source=Source()
    result=configure(1,apply=True,factory=database,client=source,pause=lambda _:None)
    assert result['status']=='activated' and len(source.calls)==4
    with database() as db:
        market=db.get(Market,2)
        assert (market.id,market.region,market.ruleset_id,market.house_id,market.source_kind,market.interval_seconds)==(2,'us',2,114,'auctions',300)
        assert market.label=='Existing market fixture' and market.unified_coverage
        assert db.scalar(select(func.count()).select_from(Market))==1
        assert db.scalar(select(func.count()).select_from(MarketFeed))==2
        assert db.scalar(select(func.count()).select_from(Observation))==1
        assert db.scalar(select(SecurityEvent.id).where(SecurityEvent.action=='market.feeds.activated'))
    assert configure(1,apply=True,factory=database,client=source,pause=lambda _:None)['status']=='already_configured'
    assert len(source.calls)==4


@pytest.mark.parametrize('case',['actor','mapping','source','campaign'])
def test_activation_guard_never_substitutes_identity_or_discards_history(database,case):
    legacy(database,mapped=case!='mapping')
    if case=='campaign':
        with database.begin() as db:
            db.add(Market(id=3,region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Other fixture',enabled=True,verified=True))
    source=Source(wrong_house=case=='source')
    with pytest.raises(ValueError):
        configure(999 if case=='actor' else 1,apply=True,factory=database,client=source,pause=lambda _:None)
    with database() as db:
        assert not db.get(Market,2).unified_coverage
        assert db.scalar(select(func.count()).select_from(MarketFeed))==0
        assert db.scalar(select(func.count()).select_from(Observation))==1
    if case!='source': assert not source.calls
