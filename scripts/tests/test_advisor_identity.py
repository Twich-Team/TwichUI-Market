"""U2 deterministic/adversarial checks. Positive equivalences are synthetic only."""
import copy
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import advisor_identity as a
import advisor_summary as u1
from advisor_identity_support import (metadata, source_context, observed, candidate, bundle,
                                     equivalence, resolver, summary_record, lookup_summary)

CORPUS = json.loads((u1.PROPOSAL / 'u2/corpus.json').read_bytes())


class IdentityU2(unittest.TestCase):
    def test_synthetic_verified_base_positive_and_default_no_trust_refusal(self):
        self.assertEqual(resolver().resolve(observed())['status'], 'insufficient_identity')
        proof = equivalence()
        result = resolver(proofs=[proof]).resolve(observed())
        self.assertEqual(result['status'], 'exact')
        self.assertEqual(result['identity'], {'item_id': 2589, 'variant_key': candidate()['variant_key']})
        self.assertEqual(result['evidence_ids'], [u1.digest(proof)])
        self.assertEqual(proof['provenance']['classification'], 'synthetic_control')
        self.assertNotIn('price', result)

    def test_source_verified_canonical_hash_vectors_and_no_native_claims(self):
        self.assertEqual(CORPUS['coverage']['native_paired_equivalences'], 0)
        self.assertEqual(CORPUS['coverage']['production_approved_equivalences'], 0)
        for row in CORPUS['upstream_hash_vectors']:
            value = a.descriptor(row['variant_json'], row['item_id'])
            self.assertEqual(hashlib.sha256(u1.canonical(value)).hexdigest(), row['variant_key'])
            self.assertTrue(row['origin_synthetic'])
        self.assertEqual(len({r['item_id'] for r in CORPUS['upstream_hash_vectors']}), 2)

    def test_existing_links_extract_id_but_cannot_establish_equivalence(self):
        for case in CORPUS['existing_links']:
            with self.subTest(case=case['id']):
                game = a.parse_link(case['link'])
                self.assertEqual(game['item_id'], 1234)
                self.assertFalse(case['native_observation'])
                data = bundle([candidate({'id': 1234})], item=1234)
                self.assertEqual(resolver(data).resolve(game)['status'], 'insufficient_identity')
                self.assertNotIn('suffix_id', game['attributes'])

    def test_all_link_fields_including_empty_and_unknown_tail_are_preserved(self):
        first = a.parse_link('item:2589::0:0:0:0:-15:0:60:0:0:0:1:9')
        self.assertEqual(first['attributes']['link_fields'][1], '')
        row = candidate({'id': 2589, 'bonus_lists': [9]})
        proof = equivalence(first, row)
        r = resolver(bundle([row]), [proof])
        self.assertEqual(r.resolve(first)['status'], 'exact')
        for suffix in (':99', ':0', ':'):
            self.assertNotEqual(r.resolve_link('item:2589::0:0:0:0:-15:0:60:0:0:0:1:9' + suffix)['status'], 'exact')
        missing = copy.deepcopy(first)
        missing['attributes']['link_fields'].pop()
        self.assertNotEqual(r.resolve(missing)['status'], 'exact')

    def test_name_is_never_identity_and_different_items_do_not_match(self):
        game = a.parse_link('|Hitem:2589:0|h[Same name]|h')
        row = candidate()
        r = resolver(proofs=[equivalence(game, row)])
        self.assertEqual(r.resolve_link('|Hitem:2589:0|h[Different display name]|h')['status'], 'exact')
        self.assertEqual(r.resolve_link('|Hitem:2590:0|h[Same name]|h')['status'], 'not_found')

    def test_item_id_alone_never_sufficient_even_single_candidate(self):
        for attrs in ({}, {'suffix_id': None}, {'item_key': None}):
            self.assertEqual(resolver(proofs=[equivalence()]).resolve({'item_id': 2589, 'attributes': attrs})['status'],
                             'insufficient_identity')

    def test_exact_different_suffixes_and_random_properties_need_separate_proofs(self):
        rows, proofs, games = [], [], []
        for number in (-15, -16, 0, 15):
            row = candidate({'id': 2589, 'synthetic_suffix': number})
            game = observed(suffix_id=number, random_property_id=number * 2)
            rows.append(row); games.append(game); proofs.append(equivalence(game, row))
        r = resolver(bundle(rows), proofs)
        for game, row in zip(games, rows):
            self.assertEqual(r.resolve(game)['identity']['variant_key'], row['variant_key'])
        changed = copy.deepcopy(games[0]); changed['attributes']['random_property_id'] = 99
        self.assertEqual(r.resolve(changed)['status'], 'ambiguous')

    def test_multiple_variants_without_equivalence_are_ambiguous(self):
        data = bundle([candidate(), candidate({'id': 2589, 'bonus_lists': [9]})])
        self.assertEqual(resolver(data).resolve(observed())['status'], 'ambiguous')

    def test_conflicting_approved_equivalences_are_ambiguous_not_filtered_away(self):
        first, second = candidate(), candidate({'id': 2589, 'bonus_lists': [9]})
        proofs = [equivalence(row=first), equivalence(row=second)]
        for candidates in ([first, second], [first]):
            self.assertEqual(resolver(bundle(candidates), proofs).resolve(observed())['status'], 'ambiguous')

    def test_hash_only_refusal_even_with_a_known_descriptor_proof(self):
        row = candidate(identity_basis='hash_only', variant_json=None)
        for proofs in ([], [equivalence()]):
            self.assertEqual(resolver(bundle([row]), proofs).resolve(observed())['reason'], 'hash_only_identity')
        row['variant_json'] = '{"id":2589}'
        self.assertEqual(resolver(bundle([row])).resolve(observed())['status'], 'invalid_input')

    def test_unknown_modifiers_and_unsupported_combinations_never_disappear(self):
        base = observed()
        proof = equivalence(base)
        for key, value in [('new_modifier', 1), ('bonus_ids', [9]),
                           ('modifiers', [{'type': 1, 'value': 7}]), ('random_property_id', 0)]:
            game = copy.deepcopy(base); game['attributes'][key] = value
            self.assertNotEqual(resolver(proofs=[proof]).resolve(game)['status'], 'exact')
        modified = observed(bonus_ids=[9, 10], modifiers=[{'type': 1, 'value': 7}])
        row = candidate({'id': 2589, 'bonus_lists': [9, 10], 'modifiers': [{'type': 1, 'value': 7}]})
        r = resolver(bundle([row]), [equivalence(modified, row)])
        self.assertEqual(r.resolve(modified)['status'], 'exact')
        modified['attributes']['bonus_ids'].reverse()
        self.assertNotEqual(r.resolve(modified)['status'], 'exact', 'No source proof permits array sorting')

    def test_contradictory_ids_suffixes_and_duplicate_modifiers_refused(self):
        cases = [observed(item_key={'itemID': 9, 'itemLevel': 0, 'itemSuffix': 0, 'battlePetSpeciesID': 0}),
                 observed(link_fields=['9']), observed(suffix_id=1, item_key=observed()['attributes']['item_key']),
                 observed(modifiers=[{'type': 1, 'value': 2}, {'type': 1, 'value': 3}])]
        for game in cases:
            self.assertEqual(resolver(proofs=[equivalence()]).resolve(game)['status'], 'invalid_input')
        self.assertEqual(resolver().resolve_link('item:2589', item_id=2)['status'], 'invalid_input')

    def test_malformed_item_links_and_oversized_fields(self):
        for link in (None, 5, '', '[not a link]', 'item:-1', 'item:0', 'item:01', 'item:1e3',
                     'item:2589:abc', 'item:2589\n', '|Hitem:2589|h[x]', 'item:2589|h[x]|h',
                     '|Hspell:2589|h[x]|h', '|Hitem:2589|h[x]|h trailing', 'item:1' + ':' * 65,
                     'item:1:' + '1' * 12, 'item:1' + ':' * 1001):
            with self.subTest(link=link):
                self.assertEqual(resolver().resolve_link(link)['status'], 'invalid_input')

    def test_item_id_integer_bounds_and_large_supported_positive(self):
        top = 2**31 - 1
        game = observed(top)
        row = candidate({'id': top})
        data = bundle([row], item=top)
        self.assertEqual(resolver(data, [equivalence(game, row)]).resolve(game)['status'], 'exact')
        for item in (0, -1, True, 2**31, 1.0, '2589', None):
            self.assertEqual(resolver().resolve({'item_id': item, 'attributes': {}})['status'], 'invalid_input')

    def test_duplicate_candidates_conflicting_descriptors_and_bad_hashes(self):
        data = bundle([candidate(), candidate()])
        self.assertEqual(resolver(data).resolve(observed())['reason'], 'duplicate_candidate_identity')
        for hash_value in ('A' * 64, 'a' * 63, 'a' * 64 + '\n', None, 'x' * 64):
            data = bundle([candidate(variant_key=hash_value)])
            self.assertEqual(resolver(data).resolve(observed())['status'], 'invalid_input')
        data = bundle([candidate({'id': 2589, 'suffix': 1}, variant_key=candidate()['variant_key'])])
        self.assertEqual(resolver(data).resolve(observed())['reason'], 'variant_hash_mismatch')

    def test_incomplete_malformed_and_noncanonical_descriptors(self):
        for text in ('{}', '{"id":9}', '{"id":2589,"id":2589}', '{ "id":2589}',
                     '{"id":2589.0}', 'null', '[2589]', '{', 'x' * 4097):
            data = bundle([candidate(variant_json=text)])
            self.assertEqual(resolver(data).resolve(observed())['status'], 'invalid_input')
        # A known hash of a truncated descriptor is still not the approved descriptor.
        full = candidate({'id': 2589, 'unknown_upstream_field': 17})
        self.assertEqual(resolver(bundle([candidate()]), [equivalence(row=full)]).resolve(observed())['status'], 'not_found')

    def test_historical_only_unsupported_and_unavailable_candidate_refused(self):
        for state in ('historical_only', 'unsupported', 'unavailable'):
            row = candidate(evidence_status=state)
            result = resolver(bundle([row]), [equivalence()]).resolve(observed())
            self.assertEqual(result['status'], 'unsupported')
            self.assertEqual(result['reason'], 'candidate_' + state)

    def test_market_fields_must_all_match_under_trusted_context(self):
        variants = {'game': 'other', 'region': 'eu', 'player_ruleset': 'PvP', 'house_id': 113,
                    'source_kind': 'commodities', 'server_market_id': 99, 'transport_ruleset_id': 2,
                    'realm_scope': 'realm', 'mapping_evidence_sha256': 'c' * 64}
        for field, value in variants.items():
            data = bundle(); data['context']['market'][field] = value
            result = resolver(data, [equivalence()]).resolve(observed())
            with self.subTest(field=field):
                self.assertIn(result['status'], ('unverified_market', 'invalid_input'))
                self.assertIsNone(result['identity'])
        data = bundle(); data['context']['issuer_id'] = '00000000-0000-4000-8000-000000000002'
        self.assertEqual(resolver(data).resolve(observed())['status'], 'unverified_market')

    def test_unverified_mapping_and_missing_mapping_evidence_fail_closed(self):
        for field, value in [('mapping_verified', False), ('mapping_evidence_sha256', None), ('player_ruleset', None)]:
            expected = source_context(); expected['market'][field] = value
            self.assertEqual(resolver(expected=expected).resolve(observed())['status'], 'unverified_market')
        # Self-asserted source verification cannot override an unverified trusted selection.
        expected = source_context(); expected['market']['mapping_verified'] = False
        self.assertEqual(resolver(expected=expected, proofs=[equivalence()]).resolve(observed())['status'], 'unverified_market')

    def test_generation_algorithm_confidence_and_local_competition_mismatch(self):
        for key, value in [('generation_id', 'c' * 64), ('pricing_algorithm', 'asking-v1-provisional'),
                           ('confidence_ceiling', 'high'), ('source_kind', 'local_scan'),
                           ('can_satisfy_local_competition', True)]:
            data = bundle(); data['context'][key] = value
            self.assertEqual(resolver(data, [equivalence()]).resolve(observed())['status'], 'invalid_input')

    def test_bundle_pin_corruption_and_unavailable_evidence(self):
        data = bundle()
        self.assertEqual(resolver(data, pin='0' * 64).resolve(observed())['reason'], 'candidate_bundle_integrity')
        r = a.Resolver(source_context(), None, expected_bundle_sha256='0' * 64)
        self.assertEqual(r.resolve(observed())['status'], 'unavailable')
        data['complete'] = False
        self.assertEqual(resolver(data).resolve(observed())['reason'], 'incomplete_candidate_set')

    def test_valid_missing_identity_never_implies_absence(self):
        result = resolver(bundle([]), [equivalence()]).resolve(observed())
        self.assertEqual(result['status'], 'not_found')
        self.assertIsNone(result['identity'])
        result = resolver(bundle([candidate({'id': 2589, 'suffix': 1})]), [equivalence()]).resolve(observed())
        self.assertEqual(result['status'], 'not_found')
        self.assertNotIn('supply', result)

    def test_proof_integrity_market_and_unknown_fields_are_not_self_authorizing(self):
        proof = equivalence(); pin = u1.digest(proof); proof['variant_json'] = '{"id":2589,"suffix":1}'
        r = a.Resolver(source_context(), bundle(), expected_bundle_sha256=u1.digest(bundle()),
                       trusted_equivalences={pin: proof})
        self.assertEqual(r.resolve(observed())['reason'], 'equivalence_integrity')
        proof = equivalence(); proof['identity_complete'] = False
        self.assertNotEqual(resolver(proofs=[proof]).resolve(observed())['status'], 'exact')
        proof = equivalence(); proof['market']['house_id'] = 113
        self.assertEqual(resolver(proofs=[proof]).resolve(observed())['status'], 'unverified_market')
        data = bundle(); data['verified'] = True
        self.assertEqual(resolver(data).resolve(observed())['status'], 'invalid_input')

    def test_candidate_proof_identity_and_depth_limits(self):
        cases = [bundle([candidate({'id': 2589, 'suffix': n}) for n in range(129)]), bundle()]
        cases[1]['candidates'][0]['variant_json'] = 'x' * 65537
        for data in cases:
            self.assertEqual(resolver(data).resolve(observed())['status'], 'invalid_input')
        proofs = [equivalence(observed(suffix_id=n), candidate({'id': 2589, 'suffix': n})) for n in range(33)]
        self.assertEqual(resolver(proofs=proofs).resolve(observed())['status'], 'invalid_input')
        game = observed(link_fields=['2589'] + ['0'] * 64)
        self.assertEqual(resolver().resolve(game)['status'], 'invalid_input')
        game = {'item_id': 2589, 'attributes': {'modifiers': [[[[[[[[[[[[[[1]]]]]]]]]]]]]]}}
        self.assertEqual(resolver().resolve(game)['status'], 'invalid_input')

    def test_malformed_optional_link_input_and_proof_market_cannot_bypass_types(self):
        r = resolver()
        self.assertEqual(r.resolve_link('item:2589', made_up=True)['status'], 'invalid_input')
        self.assertEqual(r.resolve_link('item:2589:\ud800')['status'], 'invalid_input')
        proof = equivalence(); proof['market']['mapping_verified'] = 1
        self.assertEqual(resolver(proofs=[proof]).resolve(observed())['status'], 'invalid_input')
        proof = equivalence(); proof['market']['house_id'] = True
        self.assertEqual(resolver(proofs=[proof]).resolve(observed())['status'], 'invalid_input')

    def test_corpus_market_source_fingerprints_and_unchanged_fixture_vectors(self):
        for source in CORPUS['sources']:
            if source['repository'] == 'Twich-Team/TwichUI-Market':
                path = u1.ROOT / source['path']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source['sha256'])
        for vector in CORPUS['upstream_hash_vectors']:
            g = json.loads((u1.ROOT / vector['source']).read_bytes())
            match = next(r for r in g['records'] if r['item_id'] == vector['item_id'])
            self.assertEqual((match['variant_json'], match['variant_key']),
                             (vector['variant_json'], vector['variant_key']))

    def test_inputs_snapshotted_and_results_deterministic_across_candidate_order(self):
        data = bundle([candidate(), candidate({'id': 2589, 'bonus_lists': [9]})])
        proof = equivalence(); r = resolver(data, [proof]); expected = r.resolve(observed())
        data['candidates'][0]['variant_json'] = '{}'; proof['identity_complete'] = False
        self.assertEqual(r.resolve(observed()), expected)
        rows = [candidate({'id': 2589, 'synthetic_variant': n}) for n in range(16)]
        target = observed(suffix_id=7); proof = equivalence(target, rows[7])
        for seed in range(20):
            shuffled = rows.copy(); random.Random(seed).shuffle(shuffled)
            self.assertEqual(resolver(bundle(shuffled), [proof]).resolve(target)['identity']['variant_key'], rows[7]['variant_key'])


class U1Integration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'index'

    def build(self, records):
        manifest = u1.write_index(records, metadata(), self.path)
        index = u1.Index(self.path, expected_generation_id=manifest['generation_id'])
        return index, a.context(manifest)

    def loader(self, data):
        return Mock(return_value=(data, u1.digest(data)))

    def test_exact_resolution_selects_one_u1_partition_and_preserves_tuple(self):
        rows = [candidate(), candidate({'id': 2589, 'bonus_lists': [9]})]
        source = sorted([summary_record(row) for row in rows], key=lambda r: r['variant_key'])
        index, ctx = self.build(source)
        data = bundle(rows, context=ctx); game = observed(suffix_id=-15)
        proof = equivalence(game, rows[1], context=ctx)
        load = self.loader(data)
        out = lookup_summary(index, game, load, [proof])
        self.assertEqual(out['resolution']['status'], 'exact')
        self.assertEqual(out['summary']['row'][1], rows[1]['variant_key'])
        self.assertEqual(out['summary']['row'][3:6], ['100', '110', '90'])
        self.assertEqual(out['summary']['row'][8], 0)
        load.assert_called_once_with(2589, 2589 % 64, index.manifest['generation_id'])
        self.assertEqual(index.cached_bucket, 2589 % 64)
        self.assertFalse(index.manifest['can_satisfy_local_competition'])

    def test_unresolved_never_calls_u1_lookup_or_falls_back_to_base_price(self):
        index, ctx = self.build([summary_record()])
        index.lookup = Mock(side_effect=AssertionError('unresolved must not select a price'))
        out = lookup_summary(index, observed(), self.loader(bundle(context=ctx)))
        self.assertEqual(out['resolution']['status'], 'insufficient_identity')
        self.assertEqual(out['summary'], {'state': 'unavailable', 'row': None})
        index.lookup.assert_not_called()

    def test_exact_identity_does_not_override_unknown_absent_or_missing_summary(self):
        for state, supply, complete, expected in [('unknown', None, True, 'unknown'),
                ('absent', 0, True, 'absent'), ('listed', 12, False, 'unknown')]:
            with self.subTest(state=state, complete=complete), tempfile.TemporaryDirectory() as temp:
                manifest = u1.write_index([summary_record(state=state, supply=supply, complete=complete)], metadata(), Path(temp)/'index')
                index = u1.Index(Path(temp)/'index', expected_generation_id=manifest['generation_id']); ctx = a.context(manifest)
                out = lookup_summary(index, observed(), self.loader(bundle(context=ctx)), [equivalence(context=ctx)])
                self.assertEqual(out['resolution']['status'], 'exact')
                self.assertEqual(out['summary']['state'], expected)
                self.assertEqual(out['summary']['row'][8], 1)
                self.assertIsNone(out['summary']['row'][3])
        index, ctx = self.build([])
        out = lookup_summary(index, observed(), self.loader(bundle(context=ctx)), [equivalence(context=ctx)])
        self.assertEqual(out['resolution']['status'], 'exact')
        self.assertEqual(out['summary'], {'state': 'unavailable', 'row': None})

    def test_other_generation_or_market_is_rejected_before_partition_load(self):
        index, ctx = self.build([summary_record()])
        for field, value in [('generation_id', '0' * 64), ('issuer_id', '00000000-0000-4000-8000-000000000002')]:
            data = bundle(context=copy.deepcopy(ctx)); data['context'][field] = value
            index.lookup = Mock(side_effect=AssertionError('wrong generation'))
            out = lookup_summary(index, observed(), self.loader(data), [equivalence(context=ctx)])
            self.assertNotEqual(out['resolution']['status'], 'exact')
            index.lookup.assert_not_called()
            self.assertIsNone(index.cached_bucket)

    def test_unrelated_partition_is_not_read_and_bad_requested_part_fails(self):
        index, ctx = self.build([summary_record(item=1), summary_record()])
        unrelated = next(p for p in index.manifest['partitions'] if p['bucket'] == 1)
        (self.path / unrelated['file']).write_bytes(b'corrupt')
        out = lookup_summary(index, observed(), self.loader(bundle(context=ctx)), [equivalence(context=ctx)])
        self.assertEqual(out['summary']['state'], 'priced')
        index.cached_bucket = None
        requested = next(p for p in index.manifest['partitions'] if p['bucket'] == 2589 % 64)
        (self.path / requested['file']).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            lookup_summary(index, observed(), self.loader(bundle(context=ctx)), [equivalence(context=ctx)])


if __name__ == '__main__':
    unittest.main()
