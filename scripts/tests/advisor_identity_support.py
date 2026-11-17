"""Synthetic-only U2 helpers and U1 adapter; never imported by application code."""
import copy
import hashlib
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import advisor_identity as identity
import advisor_summary as u1
from advisor_index_feasibility import generate


def metadata():
    result = generate(0)
    for field in ('records', 'records_sha256', 'record_count', 'generation_id'):
        result.pop(field)
    result['format'] = 'twichui-market-summary-partitions-u1'
    result['market'].update(mapping_verified=True, mapping_evidence_sha256='a' * 64)
    return result


def source_context():
    meta = metadata()
    meta['generation_id'] = 'b' * 64
    return identity.context(meta)


def observed(item=2589, **attributes):
    return {'item_id': item, 'attributes': attributes or {'item_key': {
        'itemID': item, 'itemLevel': 0, 'itemSuffix': 0, 'battlePetSpeciesID': 0}}}


def candidate(descriptor=None, **changes):
    text = u1.canonical({'id': 2589} if descriptor is None else descriptor).decode()
    result = {'variant_key': hashlib.sha256(text.encode()).hexdigest(),
              'variant_json': text, 'identity_basis': 'exact_upstream', 'evidence_status': 'supported'}
    result.update(changes)
    return result


def bundle(candidates=None, *, context=None, item=2589):
    return {'context': source_context() if context is None else context, 'item_id': item,
            'complete': True, 'candidates': [candidate()] if candidates is None else candidates}


def equivalence(game=None, row=None, *, context=None):
    ctx = source_context() if context is None else context
    return {'format': 'twichui-item-equivalence-u2', 'issuer_id': ctx['issuer_id'], 'market': copy.deepcopy(ctx['market']),
            'game_identity': observed() if game is None else game,
            'variant_json': candidate()['variant_json'] if row is None else row['variant_json'],
            'identity_complete': True,
            'provenance': {'classification': 'synthetic_control', 'reference': 'U2 synthetic positive control; not native proof'}}


def resolver(data=None, proofs=(), *, expected=None, pin=None):
    data = bundle() if data is None else data
    return identity.Resolver(source_context() if expected is None else expected, data,
        expected_bundle_sha256=u1.digest(data) if pin is None else pin,
        trusted_equivalences={u1.digest(p): p for p in proofs})


def summary_record(row=None, *, item=2589, state='listed', supply=12, complete=True):
    row = candidate({'id': item}) if row is None else row
    return {'item_id': item, 'variant_key': row['variant_key'], 'observation_id': '902',
            'current': {'algorithm': 'twichui-pricing-v1', 'complete': complete, 'state': state,
                'arithmetic_status': 'exact', 'supply': supply,
                'metrics': {'recent_copper': '100', 'market_value_copper': '110', 'minimum_copper': '90'}}}


def lookup_summary(index, observed_identity, candidate_loader, proofs=()):
    """TEST ONLY: one item-scoped metadata request, then one exact U1 lookup.

    Loader returns (bundle, INDEPENDENT trusted bundle pin), keyed to item/bucket/
    generation. A future publisher must establish that trust; U1 doesn't deliver it.
    """
    try:
        identity.validate_identity(observed_identity)
    except identity.Refusal as error:
        return {'resolution': {'status': error.status, 'reason': error.reason, 'identity': None},
                'summary': {'state': 'unavailable', 'row': None}}
    item = observed_identity['item_id']
    data, trusted_pin = candidate_loader(item, item % u1.BUCKETS, index.manifest['generation_id'])
    ctx = identity.context(index.manifest)
    result = identity.Resolver(ctx, data, expected_bundle_sha256=trusted_pin,
        trusted_equivalences={u1.digest(p): p for p in proofs}).resolve(observed_identity)
    summary = {'state': 'unavailable', 'row': None}
    if result['status'] == 'exact':
        exact = result['identity']
        summary = index.lookup(exact['item_id'], exact['variant_key'])
    return {'resolution': result, 'summary': summary}
