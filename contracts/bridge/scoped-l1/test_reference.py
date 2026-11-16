"""Focused conformance. Run: python3 -m unittest discover -s contracts/bridge/scoped-l1 -v"""
import copy
import hashlib
import json
from pathlib import Path
import unittest

import jsonschema
from reference import (ROOT, v1, canonical, digest, project, selection, selection_id, validate,
                       receipt, validate_receipt, preflight, sizes, lua_source, LastGood, lookup, seal, read_json, Refusal)
from build_fixtures import examples, SESSION

F = ROOT / 'fixtures'
load = lambda name: json.loads((F / name).read_text())


def mutate(value, case):
    value = copy.deepcopy(value)
    parent = value
    for k in case['path'][:-1]:
        parent = parent[k]
    k = case['path'][-1]
    if case['op'] == 'set':
        parent[k] = case['value']
    elif case['op'] == 'pop':
        parent[k].pop()
    elif case['op'] == 'append_first':
        parent[k].append(copy.deepcopy(parent[k][0]))
    return value


class Conformance(unittest.TestCase):
    def setUp(self):
        self.source = load('source.json')
        self.request = load('selection.json')
        self.good = load('scoped.json')

    def test_independent_semantics(self):
        e = load('expectations.json')
        g = validate(self.good, self.request)
        self.assertEqual([r['item_id'] for r in g['records']], e['selected_item_ids'])
        for item in e['priced_items']:
            r = next(r for r in g['records'] if r['item_id'] == item)
            self.assertEqual([d['recent_copper'] for d in r['daily']], ['100', '100'])
            self.assertEqual(r['current']['metrics']['market_value_copper'], '100')
            self.assertIsNone(r['current']['metrics']['historical_value_copper'])
        hist = g['records'][0]
        self.assertEqual((hist['current']['state'], hist['current']['supply']), ('absent', 0))
        self.assertEqual(hist['daily'][0]['recent_copper'], '100')
        bid = g['records'][3]
        self.assertEqual((bid['current']['supply'], bid['current']['priced_supply']), (10, 0))
        self.assertIsNone(bid['current']['metrics']['recent_copper'])
        self.assertEqual(g['scope']['date_coverage'][1], {'day': e['missing_day'], 'state': 'no_observation', 'observation_ref': None})
        excluded = self.source['records'][-1]
        self.assertEqual(lookup(g, excluded['item_id'], excluded['variant_key']), {'status': 'outside_scope', 'record': None})
        self.assertFalse(g['coverage']['generation_complete'])
        self.assertTrue(g['scope']['scope_complete'])

    def test_unknown_is_not_absent(self):
        g = validate(load('unknown-scoped.json'))
        self.assertIn('incomplete_only', [d['state'] for d in g['scope']['date_coverage']])
        unknown = [r for r in g['records'] if r['current']['state'] == 'unknown']
        self.assertTrue(unknown)
        for r in unknown:
            self.assertIsNone(r['current']['supply'])
            self.assertIsNone(r['current']['metrics']['recent_copper'])

    def test_unknown_cannot_turn_into_zero(self):
        g = load('unknown-scoped.json')
        g['records'][0]['current']['supply'] = 0
        g['scope']['record_sha256'] = [digest(r) for r in g['records']]
        with self.assertRaisesRegex(ValueError, 'Unknown is not zero'):
            validate(seal(g))

    def test_fixture_reproducibility(self):
        for name, value in examples().items():
            self.assertEqual((F / name).read_bytes(), canonical(value) + b'\n', name)

    def test_equivalent_order_and_duplicates(self):
        reverse = copy.deepcopy(self.request)
        reverse['variants'].reverse()
        with self.assertRaises(Refusal):
            selection(reverse)
        normalized = selection(reverse, normalize=True)
        self.assertEqual(normalized, self.request)
        self.assertEqual(project(self.source, reverse, SESSION, SESSION), self.good)

    def test_same_item_distinct_variant_is_not_aggregate(self):
        source = copy.deepcopy(self.source)
        sibling = copy.deepcopy(source['records'][1])
        sibling['variant_json'] = canonical({'id': sibling['item_id'], 'bonus': 7}).decode()
        sibling['variant_key'] = hashlib.sha256(sibling['variant_json'].encode()).hexdigest()
        source['records'].append(sibling)
        source['records'].sort(key=lambda r: (r['item_id'], r['variant_key']))
        source['record_count'] += 1
        source = v1.seal(source)
        g = project(source, self.request, SESSION, SESSION)
        self.assertEqual(lookup(g, sibling['item_id'], sibling['variant_key']), {'status': 'outside_scope', 'record': None})
        self.assertEqual(len(source['records']), 7)
        self.assertEqual(len(g['records']), 5)

    def test_window_identity_and_reuse(self):
        other = load('short-window-scoped.json')
        self.assertEqual(selection_id(self.request), selection_id(other['scope']['request']))
        self.assertNotEqual(self.good['scope']['request_digest'], other['scope']['request_digest'])
        self.assertNotEqual(self.good['generation_id'], other['generation_id'])
        self.assertEqual(project(self.source, self.request, SESSION, SESSION), self.good)
        advanced = copy.deepcopy(self.good)
        advanced['watermark_observation_id'] = str(int(advanced['watermark_observation_id']) + 1)
        self.assertNotEqual(seal(advanced)['generation_id'], self.good['generation_id'])

    def test_independent_hashes(self):
        # Independent JSON encoding + hashlib, not the reference seal/digest.
        enc = lambda x: json.dumps(x, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()
        sha = lambda x: hashlib.sha256(enc(x)).hexdigest()
        body = {k: v for k, v in self.good.items() if k not in ('generation_id', 'integrity')}
        self.assertEqual(sha(body), self.good['generation_id'])
        self.assertEqual(sha(self.request), self.good['scope']['request_digest'])
        self.assertEqual(sha(body['records']), self.good['integrity']['records_sha256'])
        self.assertEqual(sha({k: v for k, v in body.items() if k != 'records'}), self.good['integrity']['manifest_sha256'])
        self.assertEqual([sha(r) for r in body['records']], self.good['scope']['record_sha256'])

    def test_negative_fixtures(self):
        for case in load('cases.json'):
            with self.subTest(case=case['name']):
                base = self.request if case['target'] == 'request' else self.good
                bad = mutate(base, case)
                if case.get('reseal'):
                    # Rehash records and outer envelope to exercise semantics, not just corruption.
                    if case.get('refresh_record_hashes', True):
                        bad['scope']['record_sha256'] = [digest(r) for r in bad['records']]
                    bad = seal(bad)
                with self.assertRaises((ValueError, jsonschema.ValidationError)):
                    if case['target'] == 'request':
                        project(self.source, bad, SESSION, SESSION)
                    else:
                        validate(bad, self.request)

    def test_cross_account_device_and_issuer(self):
        for field, value in [('account_id', 99), ('device_id', 99), ('origin', 'https://other.invalid/')]:
            bad = {**SESSION, field: value}
            with self.assertRaisesRegex(Refusal, 'authorization'):
                project(self.source, self.request, bad, SESSION)
        bad = copy.deepcopy(self.request)
        bad['issuer_id'] = '00000000-0000-4000-8000-000000000099'
        with self.assertRaisesRegex(Refusal, 'market_authorization'):
            project(self.source, bad, SESSION, SESSION)

    def test_budget_exact_preflight_and_last_good(self):
        r = receipt(self.good)
        actual = sizes(self.good, r)
        self.assertEqual(actual['lua_bytes'], len(lua_source(self.good, r)))
        self.assertEqual(actual['canonical_bytes'], len(canonical(self.good)))
        preflight(self.good, r, {'canonical_bytes': actual['canonical_bytes'], 'lua_bytes': actual['lua_bytes']})
        state = LastGood()
        state.accept(self.good, r, self.request)
        for kind in ('canonical_bytes', 'lua_bytes', 'records'):
            with self.assertRaises(Refusal) as raised:
                state.accept(self.good, r, self.request, {kind: actual[kind] - 1})
            self.assertIn(kind, raised.exception.diagnostics['exceeded'])
            self.assertEqual(state.active, self.good)
        with self.assertRaises(Refusal):
            project(self.source, self.request, SESSION, SESSION, {'canonical_bytes': 1})
        self.assertEqual(self.source, load('source.json'), 'projection changed full archive fixture')

    def test_previous_after_interruption_and_corruption(self):
        state = LastGood()
        state.accept(self.good, receipt(self.good), self.request)
        new = load('short-window-scoped.json')
        state.accept(new, receipt(new), new['scope']['request'])
        self.assertEqual(state.previous, self.good)
        state.accept(new, receipt(new), new['scope']['request'])
        self.assertEqual(state.previous, self.good)
        for bad in ({**new, 'records': new['records'][:-1]}, {**new, 'generation_id': '0' * 64}):
            with self.assertRaises(ValueError):
                state.accept(bad, receipt(bad), new['scope']['request'])
            self.assertEqual(state.active, new)
            self.assertEqual(state.previous, self.good)

    def test_receipt_is_independent_and_bound(self):
        before = canonical(self.good)
        r = receipt(self.good)
        validate_receipt(self.good, r)
        validate_receipt(self.good, {**r, 'completed_at': '2026-11-16T13:00:00Z'})
        self.assertEqual(canonical(self.good), before)
        for bad in ({**r, 'generation_id': '0' * 64}, {**r, 'account_id': 1}, {**r, 'completed_at': '2020-01-01T00:00:00Z'}):
            with self.assertRaises(Refusal):
                validate_receipt(self.good, bad)

    def test_legacy_and_future_fail_closed(self):
        v1.validate(load('legacy-schema2.json'))
        with self.assertRaisesRegex(ValueError, 'Schema version'):
            v1.validate(self.good)
        with self.assertRaises(jsonschema.ValidationError):
            validate(load('legacy-schema2.json'))
        bad = {**self.good, 'schema_version': 4}
        with self.assertRaises(jsonschema.ValidationError):
            validate(bad)

    def test_supported_strings_unsupported_lua_number(self):
        large = load('large-money-scoped.json')
        validate(large)
        value = large['records'][1]['current']['metrics']['quantity_weighted_ask_copper']
        self.assertEqual(value, '9223372036854775807')
        self.assertGreater(int(value), 99999999999)

    def test_strict_json_read(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'bad.json'
            p.write_text('{"a":1,"a":2}')
            with self.assertRaises(Refusal):
                read_json(p)
            with self.assertRaises(Refusal):
                read_json(p, maximum=1)


if __name__ == '__main__':
    unittest.main()
