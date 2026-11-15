"""Sanitized authentic deployed-environment responses captured 2026-11-15 UTC."""
import json
from pathlib import Path
import pytest
from market.metadata_providers import parse_everloot, parse_everloot_page, parse_thewowdb
FIXTURES=Path(__file__).parent/'fixtures'/'provider-diagnostics'


def test_everloot_authentic_named_and_attribute_layers():
    body=(FIXTURES/'everloot-linen-cloth.json').read_bytes()
    fields,origin=parse_everloot(body,2589)
    assert fields=={'name':'Linen Cloth'}
    assert origin['build']=='1.60.1.70938' and origin['confidence']=='player_consensus'
    records,next_offset=parse_everloot_page((FIXTURES/'everloot-attributes-page.json').read_bytes())
    assert next_offset==1 and len(records)==1
    assert records[0][0]==17 and 'name' not in records[0][1]


def test_everloot_placeholder_does_not_become_a_name():
    value=json.loads((FIXTURES/'everloot-linen-cloth.json').read_bytes())
    value['title']='Item #2589'
    assert parse_everloot(json.dumps(value).encode(),2589)[0]=={}
    for mutation in ({'id':"2589"},{'id':2590},{'title':None},{'gameData':{'build':'12.1.5.70783'}}):
        with pytest.raises(ValueError):parse_everloot(json.dumps({**value,**mutation}).encode(),2589)


def test_thewowdb_authentic_beta_identity_and_attribution():
    value=json.loads((FIXTURES/'thewowdb-worn-shortsword.json').read_bytes())
    fields,origin=parse_thewowdb(json.dumps(value).encode(),25)
    assert fields['name']=='Worn Shortsword'
    assert origin['confidence']=='community_beta' and origin['build']=='wow_classic_beta-1.60.1.70532'
    for mutation in ({'id':26},{'version':'retail'},{'build':'wow_classic_beta-12.1.5.70783'},{'name':None},{'attribution':None}):
        with pytest.raises(ValueError):parse_thewowdb(json.dumps({**value,**mutation}).encode(),25)
