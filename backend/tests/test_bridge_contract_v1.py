import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]/'contracts/bridge/v1'
spec=importlib.util.spec_from_file_location('bridge_contract',ROOT/'validate.py')
contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)


@pytest.mark.parametrize('name',['canonical-generation.json','provisional-generation.json'])
def test_frozen_generations_and_historical_only_variants(name):
    generation=contract.read(ROOT/name)
    assert generation['records'][0]['current']['state']=='absent'
    assert generation['records'][0]['daily'][0]['recent_copper']=='50'
    assert generation['synthetic'] is True
    assert generation['market']['mapping_verified'] is False
    if generation['pricing_algorithm']=='twichui-pricing-v1':
        assert generation['records'][1]['current']['metrics']['historical_value_copper'] is None
    else:
        assert generation['records'][1]['current']['metrics']['historical_value_copper']=='110'


def changed(path,value):
    def mutation(g):
        target=g
        for key in path[:-1]:target=target[key]
        target[path[-1]]=value
    return mutation


@pytest.mark.parametrize('mutation',[
    changed(['contract_version'],2),changed(['schema_version'],2),changed(['transport_version'],2),
    changed(['pricing_algorithm'],'future'),changed(['history_basis'],'market_rolling_daily_means'),
    changed(['synthetic'],False),changed(['watermark_observation_id'],'900'),
    changed(['market','source_kind'],'commodities'),changed(['market','mapping_verified'],True),
    changed(['records',1,'variant_key'],'b'*64),changed(['records',1,'current','algorithm'],'asking-v1-provisional'),
    changed(['records',1,'current','metric_basis'],'quantity_weighted_mean'),
    changed(['records',1,'current','metrics','recent_copper'],120),
    changed(['records',1,'current','metrics','recent_copper'],'9007199254740993'),
    changed(['records',1,'current','metrics','historical_value_copper'],'100'),
    changed(['records',0,'current','supply'],1),changed(['records',1,'current','priced_supply'],11),
    changed(['records',1,'daily',0,'observation_ref'],60),
    changed(['observations',0,'scope_complete'],False),
    changed(['observations',0,'observed_at'],'2026-11-16T12:00:00Z'),
    changed(['records',1,'distribution','quartiles','anchor_copper'],'99999999999'),
    changed(['records',1,'distribution','tiers',0,'quantity'],11),
    changed(['records',1,'distribution','algorithm'],'linear-unit-price-bands-v1'),
    changed(['coverage','history_truncated'],True),changed(['coverage','delivered_observed_days'],1),
    changed(['record_count'],1),changed(['records',1,'current','supply'],10.0),
    changed(['coverage','history_from_day'],'2026-01-01'),
])
def test_reject_semantic_corruption_even_with_recomputed_hashes(mutation):
    generation=json.loads((ROOT/'canonical-generation.json').read_text());mutation(generation)
    with pytest.raises((ValueError,contract.jsonschema.ValidationError)):
        contract.validate(contract.seal(generation))


def test_integrity_duplicates_and_unknown_fields(tmp_path):
    g=json.loads((ROOT/'canonical-generation.json').read_text())
    g['generation_id']='0'*64
    with pytest.raises(ValueError):contract.validate(g)
    g=contract.seal(g);g['records'][1]['future']=True
    with pytest.raises(contract.jsonschema.ValidationError):contract.validate(contract.seal(g))
    raw=(ROOT/'canonical-generation.json').read_text().replace('"contract_version": 1','"contract_version": 1, "contract_version": 1')
    p=tmp_path/'duplicate.json';p.write_text(raw)
    with pytest.raises(ValueError):contract.read(p)
    p.write_text('{"value":NaN}')
    with pytest.raises(ValueError):contract.read(p)


def test_nesting_and_record_limits():
    value=0
    for _ in range(14):value=[value]
    with pytest.raises(ValueError):contract.canonical(value)
    g=json.loads((ROOT/'canonical-generation.json').read_text())
    # A descriptor can be syntactically valid JSON yet contradict exact identity.
    g['records'][1]['variant_json']='{"id":true}'
    import hashlib
    g['records'][1]['variant_key']=hashlib.sha256(g['records'][1]['variant_json'].encode()).hexdigest()
    with pytest.raises(ValueError):contract.validate(contract.seal(g))
