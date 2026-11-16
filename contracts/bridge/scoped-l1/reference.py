"""Offline L1 reference only. Never imported by server, desktop or addon runtime."""
import copy
from datetime import date, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent
V1_ROOT = ROOT.parent / 'v1'
spec = importlib.util.spec_from_file_location('frozen_bridge_v1', V1_ROOT / 'validate.py')
v1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v1)
canonical, digest = v1.canonical, v1.digest
MAX_BYTES = v1.MAX_BYTES
MAX_MANIFEST = 256 * 1024  # Proposed schema-3 bound only; v1 stays 64 KiB.
MAX_REQUEST = 128 * 1024
FEATURES = ['exact_copper', 'current_summaries', 'daily_history', 'scoped_selection']
DEFAULT_BUDGET = {'canonical_bytes': 2 * 1024**2, 'lua_bytes': 3 * 1024**2, 'records': 1000}


class Refusal(ValueError):
    def __init__(self, code, diagnostics=None):
        super().__init__(code)
        self.code, self.diagnostics = code, diagnostics or {}


def need(ok, code):
    if not ok:
        raise Refusal(code)


def read_json(path, maximum=MAX_BYTES):
    raw = Path(path).read_bytes()
    need(len(raw) <= maximum, 'input_bytes')
    def unique(pairs):
        result = {}
        for k, v in pairs:
            need(k not in result, 'duplicate_json_key')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(Refusal('json_constant')))


def schema(value, name):
    resources = [json.loads((V1_ROOT / 'generation-schema2.schema.json').read_text())]
    resources += [json.loads((ROOT / f).read_text()) for f in
                  ('selection.schema.json', 'generation-schema3.schema.json')]
    registry = Registry().with_resources((s['$id'], Resource.from_contents(s)) for s in resources)
    checker = jsonschema.FormatChecker()
    @checker.checks('copper-i64')
    def money(s):
        return type(s) is str and s.isascii() and s.isdigit() and len(s) <= 19 and int(s) <= 2**63 - 1
    @checker.checks('positive-i64')
    def identifier(s):
        return money(s) and int(s) > 0
    target = next(s for s in resources if s['$id'].endswith(name))
    jsonschema.Draft202012Validator(target, registry=registry, format_checker=checker).validate(value)


def key(r):
    return r['item_id'], r['variant_key']


def identities(records):
    return [{'item_id': r['item_id'], 'variant_key': r['variant_key']} for r in records]


def selection(request, normalize=False):
    """UI order may be normalized; duplicates are errors, never silently removed."""
    need(len(canonical(request)) <= MAX_REQUEST, 'request_bytes')
    schema(request, 'selection.json')
    out = copy.deepcopy(request)
    keys = [key(x) for x in out['variants']]
    need(len(keys) == len(set(keys)), 'duplicate_selection')
    if normalize:
        out['variants'].sort(key=key)
    else:
        need(keys == sorted(keys), 'selection_order')
    start, end = date.fromisoformat(out['history_from_day']), date.fromisoformat(out['history_through_day'])
    need(0 <= (end - start).days < 60, 'history_window')
    return out


def selection_id(request):
    return digest({k: v for k, v in request.items() if k not in ('history_from_day', 'history_through_day')})


def authorize(request, session, expected_session, allowed_market):
    # Trusted API/cache context supplied separately; none of these private IDs enter game bytes.
    need(session == expected_session and set(session) == {'origin', 'account_id', 'device_id'}
         and isinstance(session['origin'], str) and session['origin'].startswith('https://')
         and type(session['account_id']) is int and session['account_id'] > 0
         and type(session['device_id']) is int and session['device_id'] > 0, 'authorization')
    need((request['issuer_id'], request['market']) == allowed_market, 'market_authorization')


def date_coverage(g, request):
    result = []
    start, end = date.fromisoformat(request['history_from_day']), date.fromisoformat(request['history_through_day'])
    for offset in range((end - start).days + 1):
        day = (start + timedelta(days=offset)).isoformat()
        candidates = [(i, o) for i, o in enumerate(g['observations']) if o['utc_day'] == day]
        complete = [(i, o) for i, o in candidates if o['scope_complete']]
        selected = complete or candidates
        winner = max(selected, key=lambda x: (v1.timestamp(x[1]['observed_at']), int(x[1]['observation_id']))) if selected else None
        result.append({'day': day, 'state': 'complete_close' if complete else 'incomplete_only' if candidates else 'no_observation',
                       'observation_ref': winner[0] if winner else None})
    return result


def seal(g):
    return v1.seal(g)


def inherited_evidence(g):
    """Private validation view only, NEVER publish/cache it as a full generation.

    Reuse frozen record/time/arithmetic/distribution semantics without changing v1.
    Its generation_complete flag is a validator precondition, NOT independent proof
    of full market membership. Schema-3 membership is proved separately below.
    """
    view = copy.deepcopy(g)
    view.pop('scope')
    view['schema_version'] = 2
    view['required_features'] = FEATURES[:3]
    view['coverage']['generation_complete'] = True
    return v1.seal(view)


def validate(g, expected_request=None):
    need(len(canonical(g)) <= MAX_BYTES, 'contract_bytes')
    schema(g, 'generation-schema3.json')
    need(g['integrity'] == seal(g)['integrity'] and g['generation_id'] == seal(g)['generation_id'], 'integrity')
    manifest = {k: v for k, v in g.items() if k != 'records'}
    need(len(canonical(manifest)) <= MAX_MANIFEST, 'manifest_bytes')
    scope = g['scope']
    request = selection(scope['request'])
    need(expected_request is None or request == selection(expected_request), 'unexpected_selection')
    need(scope['request_digest'] == digest(request) and scope['selection_id'] == selection_id(request), 'selection_digest')
    need(request['issuer_id'] == g['issuer_id'] and request['market'] == g['market'], 'market_identity')
    need(request['pricing_algorithm'] == g['pricing_algorithm'] and request['history_basis'] == g['history_basis'], 'algorithm_basis')
    need(all(request[k] == g['coverage'][k] for k in ('history_from_day', 'history_through_day')), 'scope_window')
    need(identities(g['records']) == request['variants'] == scope['included'], 'scope_membership')
    need(scope['requested_count'] == g['record_count'] == len(request['variants']), 'scope_count')
    need(scope['record_sha256'] == [digest(r) for r in g['records']], 'record_integrity')
    need(scope['date_coverage'] == date_coverage(g, request), 'date_coverage')
    need(g['producer']['desktop_build'] == 'not-applicable-server-export', 'source_receipt_separation')
    # Full inherited strict semantic/integrity checks over the shared record shape.
    v1.validate(inherited_evidence(g))
    return g


def receipt(g, completed_at='2026-11-15T13:00:00Z'):
    return {'schema_version': 1, 'generation_id': g['generation_id'],
            'desktop_build': 'l1-offline-proof', 'completed_at': completed_at}


def validate_receipt(g, r):
    need(set(r) == {'schema_version', 'generation_id', 'desktop_build', 'completed_at'}
         and type(r['schema_version']) is int and r['schema_version'] == 1
         and r['generation_id'] == g['generation_id']
         and type(r['desktop_build']) is str and 1 <= len(r['desktop_build']) <= 80, 'receipt')
    import re
    need(type(r['completed_at']) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', r['completed_at']) is not None, 'receipt_time')
    need(v1.timestamp(r['completed_at']) >= v1.timestamp(g['generated_at']), 'receipt_time')


def literal(raw):
    return b'"' + b''.join(bytes([b]) if 32 <= b < 127 and b not in (34, 92)
                             else ('\\%03d' % b).encode('ascii') for b in raw) + b'"'


def lua_source(g, r):
    """Fixed test-only assignment grammar; no calls, code or server-supplied source."""
    h = {k: v for k, v in g.items() if k != 'records'}
    return (b'TwichUIMarketDataL1 = { transport_version = 1, manifest = ' + literal(canonical(h))
            + b', records = {\n' + b''.join(literal(canonical(x)) + b',\n' for x in g['records'])
            + b'}, receipt = ' + literal(canonical(r)) + b' }\n')


def sizes(g, r):
    # Exact length prediction without allocating the expanded Lua source.
    def quoted_size(raw):
        return 2 + sum(1 if 32 <= b < 127 and b not in (34, 92) else 4 for b in raw)
    header = canonical({k: v for k, v in g.items() if k != 'records'})
    parts = [canonical(x) for x in g['records']]
    lua_bytes = len(b'TwichUIMarketDataL1 = { transport_version = 1, manifest = , records = {\n}, receipt =  }\n')
    lua_bytes += quoted_size(header) + sum(quoted_size(x) + 2 for x in parts) + quoted_size(canonical(r))
    return {'canonical_bytes': len(canonical(g)), 'lua_bytes': lua_bytes, 'records': len(parts),
            'manifest_bytes': len(header), 'scope_bytes': len(canonical(g['scope'])),
            'observation_bytes': len(canonical(g['observations']))}


def preflight(g, r, budget=None):
    measured = sizes(g, r)
    hard = {'canonical_bytes': MAX_BYTES, 'manifest_bytes': MAX_MANIFEST, 'records': 1000,
            'lua_bytes': 130 * 1024**2}
    budget = DEFAULT_BUDGET if budget is None else budget
    need(set(budget) <= set(hard) and all(type(x) is int and x > 0 for x in budget.values()), 'budget')
    exceeded = {k: {'actual': measured[k], 'limit': min(hard[k], budget.get(k, hard[k]))}
                for k in hard if measured[k] > min(hard[k], budget.get(k, hard[k]))}
    if exceeded:
        raise Refusal('capacity', {'sizes': measured, 'exceeded': exceeded})
    return measured


def project(source, request, session, expected_session, budget=None):
    """Small fixture archive -> bounded projection. No production archive protocol.

    The fixture source is v1-shaped only for reuse of existing test evidence;
    production L2 must stream a normalized complete archive beyond v1 limits.
    """
    request = selection(request, normalize=True)
    authorize(request, session, expected_session, (source['issuer_id'], source['market']))
    v1.validate(source)
    need(source['coverage']['history_complete'] and not source['coverage']['history_truncated'], 'source_history_unavailable')
    need(source['coverage']['history_from_day'] <= request['history_from_day'] <= request['history_through_day'] <= source['coverage']['history_through_day'], 'source_window')
    need(request['pricing_algorithm'] == source['pricing_algorithm'] and request['history_basis'] == source['history_basis'], 'unsupported_basis')
    indexed = {key(r): r for r in source['records']}
    need(all(key(x) in indexed for x in request['variants']), 'identity_unavailable')
    g = copy.deepcopy(source)
    g['records'] = [copy.deepcopy(indexed[key(x)]) for x in request['variants']]
    for r in g['records']:
        r['daily'] = [d for d in r['daily'] if request['history_from_day'] <= g['observations'][d['observation_ref']]['utc_day'] <= request['history_through_day']]
        r['distribution'], r['distribution_status'] = None, 'omitted_budget'
    g['schema_version'], g['required_features'], g['record_count'] = 3, FEATURES[:], len(g['records'])
    g['desktop_sync_completed_at'] = None
    g['producer']['desktop_build'] = 'not-applicable-server-export'
    g['coverage'].update(generation_complete=False, distribution_complete=False, omitted_sections=['distributions'],
                         history_from_day=request['history_from_day'], history_through_day=request['history_through_day'])
    delivered = len({o['utc_day'] for o in g['observations'] if request['history_from_day'] <= o['utc_day'] <= request['history_through_day']})
    g['coverage'].update(available_observed_days=delivered, delivered_observed_days=delivered)
    g['scope'] = {'type': 'explicit_variants', 'selection_id': selection_id(request), 'request_digest': digest(request),
                  'request': request, 'requested_count': len(request['variants']), 'included': request['variants'],
                  'excluded': [], 'scope_complete': True, 'whole_market_complete': False,
                  'date_coverage': date_coverage(g, request), 'record_sha256': [digest(r) for r in g['records']]}
    g = seal(g)
    preflight(g, receipt(g), budget)
    validate(g, request)
    return g


def lookup(g, item_id, variant_key):
    ident = {'item_id': item_id, 'variant_key': variant_key}
    if ident not in g['scope']['included']:
        return {'status': 'outside_scope', 'record': None}
    return {'status': 'included', 'record': next(r for r in g['records'] if key(r) == (item_id, variant_key))}


class LastGood:
    """Test-only atomic activation model, NOT the desktop SQLite cache."""
    def __init__(self):
        self.active = None
        self.previous = None
    def accept(self, g, r, expected_request, budget=None):
        validate(g, expected_request)
        validate_receipt(g, r)
        preflight(g, r, budget)
        candidate = copy.deepcopy(g)
        if self.active is None or self.active['generation_id'] != candidate['generation_id']:
            self.previous, self.active = self.active, candidate
