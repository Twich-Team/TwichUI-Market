import json
import pytest
from market.feasibility import discover
from market.ingest import normalize


class Client:
    def authenticate(self):return 'synthetic-secret-not-printed'
    def throttle(self,meta):pass
    def transport(self,url,conditional=None,**kwargs):
        if '/ruleset/index?' in url:data={'rulesets':[{'id':1},{'id':2}]}
        elif '/auctions/?' in url:data={'auctions':[{'id':110,'name':'Fixture'}]}
        elif '/auctions/110' in url:data={'auctions':[{'id':1,'item':{'id':25},'quantity':1,'buyout':100}]}
        else:data={'id':1,'name':'Fixture','status':{'type':'UP'}}
        return {'status':304 if conditional else 200,'url':url,'headers':{'Last-Modified':'Sat, 14 Nov 2026 02:17:50 GMT'}},json.dumps(data).encode()


def test_discovery_detects_identical_ruleset_aliases_and_tests_conditionals():
    rows=list(discover('us',110,client=Client(),pause=lambda _:None))
    auctions=[r for r in rows if r.get('mapping',{}).get('source_kind')=='auctions']
    assert auctions[1]['identical_ruleset_payloads']==[1]
    assert rows[-1]['evidence']['status']==304
    assert 'If-Modified-Since' in rows[-1]['conditional_request']
    assert 'synthetic-secret-not-printed' not in json.dumps(rows)


def test_discovery_and_listing_bounds_fail_closed():
    with pytest.raises(ValueError):list(discover('attacker.invalid',110,client=Client()))
    with pytest.raises(ValueError,match='Too many listings'):normalize({'auctions':[{}]*150001},'auctions')


def test_captured_live_payload_excerpts_remain_normalizable():
    from pathlib import Path
    fixture=json.loads((Path(__file__).parent/'fixtures'/'live-us-2026-11-14.json').read_text())
    assert fixture['captured_live'] is True
    for kind in ('auctions','commodities'):
        excerpt=fixture[kind]
        assert excerpt['original_listing_count']>len(excerpt['payload']['auctions'])
        rows=normalize(excerpt['payload'],kind)
        assert len(rows)==2 and all(row['quantity']>0 for row in rows)


def test_house_overlap_comparison_reports_shared_identifiers():
    from market.feasibility import compare_houses
    class OverlapClient(Client):
        def transport(self,url,**kwargs):
            meta,body=super().transport(url.replace('/auctions/111?','/auctions/110?'),**kwargs)
            if '/auctions/?' in url:body=json.dumps({'auctions':[{'id':110,'name':'First'},{'id':111,'name':'Second'}]}).encode()
            return meta,body
    results=list(compare_houses('us',2,client=OverlapClient(),pause=lambda _:None))
    assert results[-1]['house_id_overlaps']==[{'first_house':110,'second_house':111,'shared_auction_ids':1}]
