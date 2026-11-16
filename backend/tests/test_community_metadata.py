import json
from market.community_metadata import enrich_missing,parse_community
from market.metadata import store_metadata
from market.models import ItemMetadata
import pytest


def payload():return {'id':720,'kind':'item','version':'forever','build':'wow_classic_beta-1.60.1.70532',
    'name':'Fixture Community Gloves','quality':'rare','item_level':28,'required_level':23,'vendor_sell':1070,
    'slot':'Hands','binding':'Binds when equipped','stats':[],'price':999999,
    'attribution':{'text':'Data from TheWoWDB','url':'https://thewowdb.com/wow-forever/item/brawler-gloves-720/'}}


def test_community_beta_is_attributed_and_never_supplies_market_prices():
    result=parse_community(json.dumps(payload()).encode(),720)
    assert result['source']['confidence']=='community_beta'
    assert result['source']['build'].startswith('wow_classic_beta-')
    assert result['attributes']['quality']=='RARE' and result['attributes']['vendor_sell']=='1070'
    assert 'price' not in result and 'price' not in result['attributes']
    assert result['source']['attribution']['url'].startswith('https://thewowdb.com/')


@pytest.mark.parametrize('mutation',[lambda v:v.update(version='retail'),lambda v:v.update(id=721),lambda v:v.update(build='unknown'),lambda v:v.update(attribution={'text':'Bad','url':'javascript:bad()'})])
def test_unverified_community_identity_build_or_links_fail_closed(mutation):
    value=payload();mutation(value)
    with pytest.raises(ValueError):parse_community(json.dumps(value).encode(),720)


def test_opt_in_enrichment_does_not_overwrite_primary(database,monkeypatch):
    from market.metadata_recovery import ensure_providers
    from market.models import MetadataProvider
    with database.begin() as db:
        ensure_providers(db);db.get(MetadataProvider,'thewowdb').enabled=True
    called=[]
    def fetch(url,**kwargs):called.append(url);return {'status':200,'headers':{'ETag':'fixture'}},json.dumps(payload()).encode()
    with database.begin() as db:
        row=ItemMetadata(region='us',item_id=720,namespace='static-forever-us',status='missing')
        db.add(row)
        monkeypatch.setenv('ITEM_COMMUNITY_FALLBACK_ENABLED','false')
        assert not enrich_missing(row,transport=fetch) and called==[]
        monkeypatch.setenv('ITEM_COMMUNITY_FALLBACK_ENABLED','true')
        assert enrich_missing(row,transport=fetch)
        assert row.name is None and row.fallback_name=='Fixture Community Gloves'
        assert not enrich_missing(row,transport=fetch)
        store_metadata(db,'us',720,b'{"id":720,"name":"Primary Name"}',synthetic=True)
        assert not enrich_missing(row,transport=fetch) and row.name=='Primary Name'
