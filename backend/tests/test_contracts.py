from datetime import datetime
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator,FormatChecker
from referencing import Registry,Resource
from market.ingest import ingest
from market.models import Market

ROOT=Path(__file__).resolve().parents[2]/'contracts'
checker=FormatChecker()


@checker.checks('copper-i64')
def copper(value):
    return value is None or (isinstance(value,str) and value.isascii() and value.isdigit() and int(value)<=2**63-1)


@checker.checks('date-time')
def timestamp(value):
    if value is None:return True
    try:return isinstance(value,str) and 'T' in value and datetime.fromisoformat(value.replace('Z','+00:00')).tzinfo is not None
    except ValueError:return False


def validator(name):
    schemas=[json.loads(path.read_text()) for path in (ROOT/'v1').glob('*.schema.json')]
    registry=Registry().with_resources((schema['$id'],Resource.from_contents(schema)) for schema in schemas)
    for schema in schemas:Draft202012Validator.check_schema(schema)
    schema=next(schema for schema in schemas if schema['$id']==f'urn:twichui-market:{name}:v1')
    return Draft202012Validator(schema,registry=registry,format_checker=checker)


def test_shared_synthetic_sync_and_export_fixtures():
    for name in ('sync-page','addon-export'):
        data=json.loads((ROOT/'fixtures'/f'{name}-v1.json').read_text())
        validator(name).validate(data)
        assert data['synthetic']
        data['execute']='forbidden executable field'
        assert not validator(name).is_valid(data)


def test_actual_private_sync_response_matches_the_shared_schema(owner,database,monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET','synthetic-contract-signing-key-32-characters')
    with database.begin() as db:
        market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Synthetic wire contract')
        db.add(market);db.flush();market_id=market.id
        ingest(db,market_id,b'{"auctions":[{"id":1,"item":{"id":12363},"quantity":1,"buyout":9007199254740993}]}',request_key='wire',synthetic=True)
    response=owner.get(f'/api/v1/sync/markets/{market_id}').json()
    validator('sync-page').validate(response)
    assert response['changes'][0]['value']['recent_price']=='9007199254740993'
    with database.begin() as db:
        empty=Market(region='eu',ruleset_id=2,house_id=114,source_kind='auctions',label='Empty contract fixture')
        db.add(empty);db.flush();empty_id=empty.id
    blank=owner.get(f'/api/v1/sync/markets/{empty_id}').json()
    validator('sync-page').validate(blank)
    assert blank['target_observation_id']=='0' and blank['observed_at'] is None


@pytest.mark.parametrize('mutation',[
    lambda data:data['changes'][0]['value'].__setitem__('recent_price',9007199254740993),
    lambda data:data['changes'][0]['value'].__setitem__('recent_price','9223372036854775808'),
    lambda data:data['changes'][0]['value'].pop('historical_value'),
    lambda data:data.__setitem__('contract_version',2),
    lambda data:data.__setitem__('observed_at','not-a-timestamp'),
    lambda data:data['changes'][1].__setitem__('value',data['changes'][0]['value']),
])
def test_shared_contract_rejects_precision_loss_missing_fields_and_unknown_versions(mutation):
    data=json.loads((ROOT/'fixtures'/'sync-page-v1.json').read_text())
    mutation(data)
    assert not validator('sync-page').is_valid(data)
