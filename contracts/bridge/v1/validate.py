"""Offline frozen-contract conformance; no delivery or application integration."""
import argparse
import copy
from datetime import date, datetime
import hashlib
import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent
MAX_BYTES = 32 * 1024 * 1024
MAX_RECORD_BYTES = 64 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
ALGORITHMS = {'twichui-pricing-v1':'canonical_complete_scope_close',
              'asking-v1-provisional':'market_rolling_daily_means'}


def canonical(value, depth=0):
    if depth>12: raise ValueError('Nesting limit')
    if type(value) is float: raise ValueError('Floating point is not part of the contract')
    if isinstance(value,dict):
        for k,v in value.items():
            if type(k) is not str: raise ValueError('JSON key')
            canonical(v, depth+1)
    elif isinstance(value,list):
        for v in value: canonical(v, depth+1)
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


def digest(value): return hashlib.sha256(canonical(value)).hexdigest()


def seal(generation):
    g=copy.deepcopy(generation);g.pop('generation_id',None);g.pop('integrity',None)
    records=canonical(g['records']);manifest={k:v for k,v in g.items() if k!='records'}
    g['generation_id']=digest(g)
    g['integrity']={'records_bytes':len(records),'records_sha256':hashlib.sha256(records).hexdigest(),'manifest_sha256':digest(manifest)}
    return g


def timestamp(value): return datetime.fromisoformat(value.replace('Z','+00:00'))


def validate(g):
    if len(canonical(g)) > MAX_BYTES: raise ValueError('Generation byte limit')
    checker=jsonschema.FormatChecker()
    @checker.checks('copper-i64')
    def copper(value): return type(value) is str and len(value)<=19 and value.isascii() and value.isdigit() and int(value)<=2**63-1
    @checker.checks('positive-i64')
    def identifier(value): return copper(value) and int(value)>0
    version=g.get('schema_version')
    if type(version) is not int or version not in (1,2): raise ValueError('Schema version')
    schema=json.loads((ROOT/('generation.schema.json' if version==1 else 'generation-schema2.schema.json')).read_text())
    jsonschema.Draft202012Validator(schema,format_checker=checker).validate(g)
    expected=seal(g)
    if expected['integrity']!=g['integrity'] or expected['generation_id']!=g['generation_id']: raise ValueError('Generation integrity')
    manifest={k:v for k,v in g.items() if k not in ('records','integrity','generation_id')}
    if len(canonical(manifest))>MAX_MANIFEST_BYTES: raise ValueError('Manifest byte limit')
    if len(g['records'])!=g['record_count']: raise ValueError('Record count')
    at=timestamp(g['generated_at']);sync=timestamp(g['desktop_sync_completed_at']) if g['desktop_sync_completed_at'] is not None else None
    if (sync is not None and sync>at) or (g['server_checked_at'] and timestamp(g['server_checked_at'])>at): raise ValueError('Delivery timestamps')
    if g['as_of_utc_day']>at.date().isoformat(): raise ValueError('Future as-of date')
    market=g['market'];coverage=g['coverage'];algorithm=g['pricing_algorithm']
    if (market['source_kind']=='auctions')!=(coverage['scope']=='house_auctions'): raise ValueError('Source scope')
    if market['mapping_verified'] and (market['mapping_evidence_sha256'] is None or market['player_ruleset'] is None): raise ValueError('Mapping evidence')
    if coverage['history_from_day']>coverage['history_through_day'] or coverage['history_through_day']>g['as_of_utc_day']: raise ValueError('History window')
    if not 0<=(date.fromisoformat(g['as_of_utc_day'])-date.fromisoformat(coverage['history_from_day'])).days<60: raise ValueError('History retention window')
    if coverage['delivered_observed_days']>coverage['available_observed_days']: raise ValueError('Coverage count')
    if coverage['history_complete'] and coverage['history_truncated']: raise ValueError('History completeness')
    if coverage['history_complete'] and coverage['delivered_observed_days']!=coverage['available_observed_days']: raise ValueError('Complete history count')
    if coverage['history_truncated'] and 'older_daily_history' not in coverage['omitted_sections']: raise ValueError('Omission reason')
    observations=g['observations'];seen_obs=set()
    for o in observations:
        if o['observation_id'] in seen_obs or int(o['observation_id'])>int(g['watermark_observation_id']): raise ValueError('Observation identity')
        seen_obs.add(o['observation_id'])
        if timestamp(o['observed_at'])>at or timestamp(o['observed_at']).date().isoformat()!=o['utc_day']: raise ValueError('Observation timestamp')
        if o['upstream_updated_at'] and timestamp(o['upstream_updated_at'])>at: raise ValueError('Upstream timestamp')
        if o['synthetic'] and not g['synthetic']: raise ValueError('Synthetic provenance')
    delivered={o['utc_day'] for o in observations if coverage['history_from_day']<=o['utc_day']<=coverage['history_through_day']}
    if len(delivered)!=coverage['delivered_observed_days']: raise ValueError('Delivered coverage')
    def observation(ref):
        if ref is None:return None
        if ref>=len(observations): raise ValueError('Observation reference')
        return observations[ref]
    current=observation(g['current_observation_ref'])
    if g['records'] and current is None: raise ValueError('Current observation missing')
    if current and coverage['current_complete']!=current['scope_complete']: raise ValueError('Current completeness')
    if current and current is not max(observations,key=lambda o:(timestamp(o['observed_at']),int(o['observation_id']))): raise ValueError('Current chronology')
    identities=set();previous=None
    for r in g['records']:
        if len(canonical(r))>MAX_RECORD_BYTES: raise ValueError('Record byte limit')
        key=(r['item_id'],r['variant_key'])
        if key in identities or (previous is not None and key<=previous): raise ValueError('Record identity/order')
        identities.add(key);previous=key
        if r['identity_basis']=='exact_upstream':
            if r['variant_json'] is None or hashlib.sha256(r['variant_json'].encode()).hexdigest()!=r['variant_key']: raise ValueError('Variant hash')
            descriptor=json.loads(r['variant_json'])
            if type(descriptor) is not dict or type(descriptor.get('id')) is not int or canonical(descriptor).decode()!=r['variant_json'] or descriptor['id']!=r['item_id']: raise ValueError('Variant descriptor')
        elif r['variant_json'] is not None: raise ValueError('Hash-only descriptor')
        c=r['current'];obs=observation(c['observation_ref'])
        if c['observation_ref']!=g['current_observation_ref'] or c['algorithm']!=algorithm: raise ValueError('Current generation/algorithm')
        basis='lower_band_mean' if algorithm=='twichui-pricing-v1' else 'quantity_weighted_mean'
        if c['metric_basis']!=basis: raise ValueError('Metric basis')
        if c['complete'] and (obs is None or not obs['scope_complete']): raise ValueError('Current completeness')
        def values(x,prices,source):
            if x['state']=='unknown':
                if any(x[k] is not None for k in ('supply','priced_supply','listing_count')) or any(v is not None for v in prices): raise ValueError('Unknown is not zero')
            else:
                if any(x[k] is None for k in ('supply','priced_supply','listing_count')): raise ValueError('Known counts')
                if x['priced_supply']>x['supply']: raise ValueError('Priced supply')
                if x['state']=='absent' and (not source or not source['scope_complete'] or any(x[k]!=0 for k in ('supply','priced_supply','listing_count')) or any(v is not None for v in prices)): raise ValueError('Absence proof')
                if x['priced_supply']==0 and any(v is not None for v in prices): raise ValueError('Unpriced data')
            if x['arithmetic_status']=='unsupported' and any(v is not None for v in prices): raise ValueError('Unsupported arithmetic')
            if algorithm=='twichui-pricing-v1':
                if any(v is not None and not 1<=int(v)<=99999999999 for v in prices): raise ValueError('Canonical price range')
        values(c,[c['metrics']['minimum_copper'],c['metrics']['recent_copper']],obs)
        cov=c['coverage']
        if cov['priced_days_14']>cov['priced_days_60'] or cov['priced_days_60']>cov['observed_days_60']: raise ValueError('Reference coverage')
        if algorithm=='twichui-pricing-v1':
            for name in ('minimum_copper','recent_copper','market_value_copper','historical_value_copper'):
                value=c['metrics'][name]
                if value is not None and not 1<=int(value)<=99999999999: raise ValueError('Canonical price range')
            if cov['priced_days_14']>14 or cov['priced_days_60']>60: raise ValueError('Calendar coverage')
            if c['metrics']['historical_value_copper'] is not None and cov['priced_days_60']<3: raise ValueError('Historical coverage')
        seen_days=set();last_day=None
        for d in r['daily']:
            source=observation(d['observation_ref']);day=source['utc_day']
            if day in seen_days or (last_day is not None and day<=last_day): raise ValueError('Daily identity/order')
            seen_days.add(day);last_day=day
            if not coverage['history_from_day']<=day<=coverage['history_through_day']: raise ValueError('Daily window')
            if d['algorithm']!=algorithm: raise ValueError('History algorithm')
            if algorithm=='twichui-pricing-v1' and not source['scope_complete']: raise ValueError('Canonical close completeness')
            if algorithm=='twichui-pricing-v1':
                close=max((o for o in observations if o['utc_day']==day and o['scope_complete']),key=lambda o:(timestamp(o['observed_at']),int(o['observation_id'])))
                if source is not close: raise ValueError('Canonical daily close selection')
            values(d,[d['minimum_copper'],d['recent_copper']],source)
        if coverage['history_complete']:
            eligible={o['utc_day'] for o in observations if coverage['history_from_day']<=o['utc_day']<=coverage['history_through_day']
                      and (algorithm!='twichui-pricing-v1' or o['scope_complete'])}
            if seen_days!=eligible: raise ValueError('Claimed complete daily history omits an eligible date')
        dist=r['distribution']
        if (dist is not None)!=(r['distribution_status']=='available'): raise ValueError('Distribution availability')
        if coverage['distribution_complete'] and c['priced_supply'] and dist is None: raise ValueError('Distribution coverage')
        if dist is not None:
            wanted='canonical-tiers-v1' if algorithm=='twichui-pricing-v1' else 'linear-unit-price-bands-v1'
            if dist['algorithm']!=wanted or c['state']!='listed': raise ValueError('Distribution algorithm/scope')
            if dist['priced_supply']!=c['priced_supply'] or dist['priced_supply']+dist['unpriced_supply']!=c['supply'] or dist['priced_listing_count']+dist['unpriced_listing_count']!=c['listing_count']: raise ValueError('Distribution totals')
            if dist['complete'] and dist['truncated']: raise ValueError('Distribution completeness')
            if wanted=='canonical-tiers-v1':
                if dist['quartiles'] is None or dist['bands']: raise ValueError('Canonical distribution basis')
                q=dist['quartiles'];ordered=[int(q[k]) for k in ['q25_copper','q50_copper','q75_copper','high_copper']]
                if ordered!=sorted(ordered) or any(not 1<=v<=99999999999 for v in ordered): raise ValueError('Quartiles')
                if not int(q['q25_copper'])<=int(q['anchor_copper'])<=int(q['q50_copper']): raise ValueError('Anchor')
                if c['metrics']['minimum_copper'] is None or c['metrics']['recent_copper'] is None or not int(c['metrics']['minimum_copper'])<=int(c['metrics']['recent_copper'])<=int(q['q50_copper']): raise ValueError('Distribution/price bounds')
                previous_price=0
                for t in dist['tiers']:
                    p=int(t['unit_copper'])
                    if not previous_price<p<=99999999999 or t['listing_count']>t['quantity'] or t['largest_listing']>t['quantity']: raise ValueError('Tier semantics')
                    previous_price=p
                if sum(t['quantity'] for t in dist['tiers'])+dist['tail_quantity']!=dist['priced_supply'] or sum(t['listing_count'] for t in dist['tiers'])+dist['tail_listing_count']!=dist['priced_listing_count']: raise ValueError('Tier totals')
            else:
                if dist['quartiles'] is not None or dist['tiers'] or dist['tail_quantity'] or dist['tail_listing_count']: raise ValueError('Provisional bins are not tiers')
                if any(int(b['minimum_copper'])>int(b['maximum_copper']) for b in dist['bands']): raise ValueError('Band bounds')
                if sum(b['supply'] for b in dist['bands'])!=dist['priced_supply'] or sum(b['listing_count'] for b in dist['bands'])!=dist['priced_listing_count']: raise ValueError('Band totals')
    return g


def read(path):
    raw=Path(path).read_bytes()
    if len(raw)>MAX_BYTES: raise ValueError('Generation file limit')
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out: raise ValueError('Duplicate JSON key')
            out[k]=v
        return out
    g=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda v: (_ for _ in ()).throw(ValueError('JSON constant')))
    return validate(g)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('files',nargs='+');args=ap.parse_args()
    for path in args.files:
        result=read(path);print(path,result['generation_id'],'VALID')
