"""Offline U1 behavior/integrity checks; no application services or client."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import advisor_summary as u
from advisor_index_feasibility import generate, validate


def metadata():
    g = generate(0)
    for key in ('records', 'records_sha256', 'record_count', 'generation_id'):
        g.pop(key)
    g.update(format='twichui-market-summary-partitions-u1')
    return g


def record(item=2589, variant=None, **changes):
    result = {'observation_id': '902', 'item_id': item,
              'variant_key': variant or hashlib.sha256(u.canonical({'id': item})).hexdigest(),
              'current': {'algorithm': 'twichui-pricing-v1', 'state': 'listed', 'complete': True,
                          'arithmetic_status': 'exact', 'supply': 12,
                          'metrics': {'recent_copper': '100', 'market_value_copper': '110', 'minimum_copper': '90'}}}
    result['current'].update(changes)
    return result


class SummaryU1(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.meta = metadata()

    def build(self, rows, name='index', **options):
        dest = self.root / name
        manifest = u.write_index(iter(rows), self.meta, dest, **options)
        return dest, manifest, u.Index(dest, expected_generation_id=manifest['generation_id'])

    def reseal(self, path, manifest):
        manifest['generation_id'] = u.digest({k: v for k, v in manifest.items() if k != 'generation_id'})
        (path / 'manifest.json').write_bytes(u.canonical(manifest))
        return manifest['generation_id']

    def replace_rows(self, path, manifest, rows):
        part = manifest['partitions'][0]
        raw = u.canonical(rows)
        part.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        part['file'] = f"{part['bucket']:02d}-{part['sha256']}.json"
        (path / part['file']).write_bytes(raw)
        return self.reseal(path, manifest)

    def test_empty_and_missing_are_unavailable_even_with_complete_source(self):
        path, manifest, index = self.build([])
        self.assertEqual(manifest['record_count'], 0)
        self.assertEqual(manifest['partitions'], [])
        self.assertEqual(index.lookup(2589, '0' * 64), {'state': 'unavailable', 'row': None})
        self.assertTrue(index.verify_all())

    def test_exact_variants_share_partition_but_never_merge(self):
        rows = [record(2589, '0' * 64), record(2589, '1' * 64, supply=13)]
        _, manifest, index = self.build(rows)
        self.assertEqual(len(manifest['partitions']), 1)
        self.assertEqual(index.lookup(2589, '0' * 64)['row'][6], 12)
        self.assertEqual(index.lookup(2589, '1' * 64)['row'][6], 13)
        self.assertEqual(index.lookup(2589, '2' * 64)['state'], 'unavailable')
        # Reader returns a copy, so callers cannot mutate its validated cache.
        index.lookup(2589, '0' * 64)['row'][6] = 99
        self.assertEqual(index.lookup(2589, '0' * 64)['row'][6], 12)

    def test_source_projection_reuses_existing_canonical_bridge_fixture(self):
        g = json.loads((u.ROOT / 'contracts/bridge/v1/source-canonical-generation.json').read_bytes())
        current = next(r for r in g['records'] if r['current']['state'] == 'listed')
        row = u.project_record(dict(current, observation_id='902'), self.meta)
        self.assertEqual(row[:2], [current['item_id'], current['variant_key']])
        self.assertEqual(row[3:6], [current['current']['metrics'][k] for k in
                                  ('recent_copper', 'market_value_copper', 'minimum_copper')])
        self.assertEqual(row[7], 120)

    def test_same_rows_conform_to_unchanged_proposal(self):
        g = generate(5)
        for row in g['records']:
            row[7] = 120
            u.validate_row(row, self.meta)
        # Preserve and execute the original feasibility validator too.
        self.assertTrue(validate(generate(5)))

    def test_sparse_metrics_and_supply_only(self):
        r = record(metrics={'recent_copper': None, 'market_value_copper': '110', 'minimum_copper': None})
        self.assertEqual(u.project_record(r, self.meta)[3:6], [None, '110', None])
        r['current']['metrics']['market_value_copper'] = None
        row = u.project_record(r, self.meta)
        self.assertEqual(row[2], 1)
        self.assertEqual(row[6], 12)
        self.assertEqual(row[8], 1)

    def test_noncanonical_copper_newlines_and_false_absence_refused(self):
        r = record()
        r['current']['metrics']['recent_copper'] = '100\n'
        with self.assertRaises(ValueError):
            u.project_record(r, self.meta)
        for supply in (False, 0.0, None, 1):
            with self.subTest(supply=supply), self.assertRaises(ValueError):
                u.project_record(record(state='absent', supply=supply), self.meta)
        self.meta['market']['mapping_evidence_sha256'] = '0' * 64 + '\n'
        with self.assertRaises(ValueError):
            u.validate_metadata(self.meta)

    def test_missing_current_metadata_remains_unknown(self):
        r = record()
        r.pop('current')
        row = u.project_record(r, self.meta)
        self.assertEqual(row[2:7], [3, None, None, None, None])
        self.assertEqual(row[8], 1)

    def test_missing_required_identity_or_market_metadata_refused(self):
        for key in ('market', 'issuer_id', 'source_observation', 'generated_at'):
            with self.subTest(key=key):
                bad = copy.deepcopy(self.meta)
                bad.pop(key)
                with self.assertRaises((ValueError, KeyError, u.jsonschema.ValidationError)):
                    u.write_index([], bad, self.root / key)
        r = record()
        r.pop('variant_key')
        with self.assertRaises(KeyError):
            self.build([r])

    def test_complete_absence_and_incomplete_source(self):
        absent = record(state='absent', supply=0)
        self.assertEqual(u.project_record(absent, self.meta)[2:7], [2, None, None, None, 0])
        for source_complete, current_complete in ((False, True), (True, False), (False, False)):
            self.meta['source_observation']['scope_complete'] = source_complete
            absent['current']['complete'] = current_complete
            self.assertEqual(u.project_record(absent, self.meta)[2:7], [3, None, None, None, None])
            listed = record(complete=current_complete)
            self.assertEqual(u.project_record(listed, self.meta)[2], 3)

    def test_partial_universe_coverage_is_explicit_and_missing_unavailable(self):
        self.meta['coverage']['complete'] = False
        _, manifest, index = self.build([record()])
        self.assertFalse(manifest['coverage']['complete'])
        self.assertEqual(index.lookup(2589, '0' * 64)['state'], 'unavailable')

    def test_maximum_supported_copper_exact_and_oversized_never_rounded(self):
        r = record()
        r['current']['metrics'] = dict.fromkeys(r['current']['metrics'], str(u.MAX_COPPER))
        _, _, index = self.build([r])
        self.assertEqual(index.lookup(2589, r['variant_key'])['row'][3:6], [str(u.MAX_COPPER)] * 3)
        for value in ('9007199254740993', '9223372036854775807', '0', '01', '1e3', 100.0, True):
            r['current']['metrics']['recent_copper'] = value
            with self.subTest(value=value), self.assertRaises(u.jsonschema.ValidationError):
                u.project_record(r, self.meta)
        r['current']['arithmetic_status'] = 'unsupported'
        self.assertEqual(u.project_record(r, self.meta)[2:7], [4, None, None, None, None])

    def test_duplicate_and_unsorted_identity_refused_without_output(self):
        for rows in ([record(), record()], [record(2), record(1)]):
            with self.assertRaisesRegex(ValueError, 'unique and ordered'):
                self.build(rows)
            self.assertFalse((self.root / 'index').exists())
            self.assertEqual(list(self.root.iterdir()), [])

    def test_highly_skewed_variants_refuse_without_pruning_or_publication(self):
        rows = (record(2589, f'{n:064x}') for n in range(5000))
        with self.assertRaisesRegex(ValueError, 'Bucket 29 exceeds.*no variants published'):
            self.build(rows)
        self.assertFalse((self.root / 'index').exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_small_explicit_partition_limit_and_record_count_limit(self):
        with self.assertRaisesRegex(ValueError, 'exceeds 128 bytes'):
            self.build([record(1), record(65)], max_partition_bytes=128)
        from unittest.mock import patch
        with patch.object(u, 'MAX_RECORDS', 1), self.assertRaisesRegex(ValueError, 'record limit'):
            self.build([record(1), record(2)])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_generation_is_never_replaced(self):
        path, manifest, _ = self.build([record()])
        with self.assertRaises(FileExistsError):
            u.write_index([], self.meta, path)
        self.assertEqual(u.read_manifest(path, expected_generation_id=manifest['generation_id']), manifest)

    def test_deterministic_rebuild_and_incremental_change_locality(self):
        rows = [record(n) for n in range(1, 257)]
        path, first, _ = self.build(rows)
        other, second, _ = self.build(rows, 'second')
        self.assertEqual(first, second)
        for file in path.iterdir():
            self.assertEqual(file.read_bytes(), (other / file.name).read_bytes())
        rows[0]['current']['metrics']['recent_copper'] = '101'
        _, changed, _ = self.build(rows, 'changed')
        self.assertEqual(sum(a['sha256'] != b['sha256'] for a, b in zip(first['partitions'], changed['partitions'])), 1)
        self.assertNotEqual(first['generation_id'], changed['generation_id'])

    def test_lookup_does_not_read_unrelated_corrupt_partition(self):
        path, manifest, index = self.build([record(1), record(2)])
        part = manifest['partitions'][1]
        (path / part['file']).write_bytes(b'corrupt')
        self.assertEqual(index.lookup(1, record(1)['variant_key'])['state'], 'priced')
        with self.assertRaises((ValueError, json.JSONDecodeError)):
            index.lookup(2, record(2)['variant_key'])
        self.assertIsNone(index.cached_bucket)
        with self.assertRaises((ValueError, json.JSONDecodeError)):
            index.verify_all()

    def test_manifest_tamper_wrong_pin_and_source_mismatch_fail(self):
        path, manifest, _ = self.build([record()])
        with self.assertRaisesRegex(ValueError, 'integrity'):
            u.Index(path, expected_generation_id='0' * 64)
        manifest['source_watermark'] = '903'
        (path / 'manifest.json').write_bytes(u.canonical(manifest))
        with self.assertRaisesRegex(ValueError, 'integrity'):
            u.Index(path, expected_generation_id=manifest['generation_id'])
        r = record()
        r['observation_id'] = '901'
        with self.assertRaisesRegex(ValueError, 'different source'):
            u.project_record(r, self.meta)

    def test_partition_tamper_missing_truncation_and_oversized_fail(self):
        for label, raw in (('price', b'[]'), ('truncated', b'['), ('large', b' ' * (u.MAX_PART_BYTES + 1))):
            path, manifest, index = self.build([record()], label)
            (path / manifest['partitions'][0]['file']).write_bytes(raw)
            with self.subTest(label=label), self.assertRaises(ValueError):
                index.verify_all()
        path, manifest, index = self.build([record()], 'missing')
        (path / manifest['partitions'][0]['file']).unlink()
        with self.assertRaises(FileNotFoundError):
            index.verify_all()

    def test_rehashed_wrong_route_order_count_and_row_semantics_fail(self):
        for label in ('route', 'duplicate', 'age', 'unknown_zero', 'confidence', 'absent_incomplete', 'count'):
            path, manifest, _ = self.build([record()], label)
            rows = json.loads((path / manifest['partitions'][0]['file']).read_bytes())
            if label == 'route': rows[0][0] += 1
            if label == 'duplicate':
                rows.append(rows[0].copy())
                manifest['partitions'][0]['record_count'] = 2
                manifest['record_count'] = 2
            if label == 'age': rows[0][7] += 1
            if label == 'unknown_zero': rows[0][2:7] = [3, None, None, None, 0]
            if label == 'confidence': rows[0][8] = 1
            if label == 'absent_incomplete':
                rows[0][2:] = [2, None, None, None, 0, 120, 1]
                manifest['source_observation']['scope_complete'] = False
            if label == 'count':
                manifest['partitions'][0]['record_count'] = 2
                manifest['record_count'] = 2
            pin = self.replace_rows(path, manifest, rows)
            with self.subTest(label=label), self.assertRaises(ValueError):
                u.Index(path, expected_generation_id=pin).verify_all()

    def test_closed_schema_version_provenance_and_path_fail_even_rehashed(self):
        mutations = [('schema_version', 2), ('experimental', False),
                     ('can_satisfy_local_competition', True), ('source_kind', 'local_scan'),
                     ('confidence_ceiling', 'high'), ('new_field', 1)]
        for key, value in mutations:
            path, manifest, _ = self.build([record()], key)
            manifest[key] = value
            pin = self.reseal(path, manifest)
            with self.subTest(key=key), self.assertRaises(u.jsonschema.ValidationError):
                u.Index(path, expected_generation_id=pin)
        path, manifest, _ = self.build([record()], 'path')
        manifest['partitions'][0]['file'] = '../unsafe.json'
        pin = self.reseal(path, manifest)
        with self.assertRaises(u.jsonschema.ValidationError):
            u.Index(path, expected_generation_id=pin)

    def test_timestamp_mapping_watermark_and_boolean_integer_failures(self):
        for edit in ('future', 'naive', 'mapping', 'watermark', 'complete'):
            bad = copy.deepcopy(self.meta)
            if edit == 'future': bad['generated_at'] = '2026-11-14T12:02:00Z'
            if edit == 'naive': bad['generated_at'] = '2026-11-15T12:02:00'
            if edit == 'mapping': bad['market']['mapping_verified'] = True
            if edit == 'watermark': bad['source_watermark'] = '1'
            if edit == 'complete': bad['source_observation']['scope_complete'] = 1
            with self.subTest(edit=edit), self.assertRaises((ValueError, u.jsonschema.ValidationError)):
                u.validate_metadata(bad)
        for value in (True, 12.0, -1, 2**53):
            with self.subTest(value=value), self.assertRaises(ValueError):
                u.project_record(record(supply=value), self.meta)

    def test_invalid_hash_grammar_and_unsorted_rehashed_rows_refused(self):
        for variant in ('a' * 64 + '\n', 'A' * 64, 'a' * 63):
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                u.project_record(record(variant=variant), self.meta)
        path, manifest, _ = self.build([record(1), record(65)])
        part = manifest['partitions'][0]
        rows = json.loads((path / part['file']).read_bytes())
        rows.reverse()
        pin = self.replace_rows(path, manifest, rows)
        with self.assertRaisesRegex(ValueError, 'order'):
            u.Index(path, expected_generation_id=pin).verify_all()

    def test_rehashed_manifest_counts_duplicate_buckets_and_size_limits_refused(self):
        for label in ('count', 'duplicate', 'limit', 'filename'):
            path, manifest, _ = self.build([record()], label)
            if label == 'count': manifest['record_count'] += 1
            if label == 'duplicate':
                manifest['partitions'].append(manifest['partitions'][0].copy())
                manifest['record_count'] = 2
            if label == 'limit': manifest['partitioning']['max_partition_bytes'] = 128
            if label == 'filename': manifest['partitions'][0]['file'] = '01-' + '0' * 64 + '.json'
            # A tiny source part fits 128 B; explicitly declare an over-bound part.
            if label == 'limit': manifest['partitions'][0]['bytes'] = 129
            pin = self.reseal(path, manifest)
            with self.subTest(label=label), self.assertRaises(ValueError):
                u.Index(path, expected_generation_id=pin)

    def test_duplicate_json_keys_noncanonical_and_manifest_size_refused(self):
        for label, raw in (('duplicate', b'{"x":1,"x":2}'), ('space', b' []'),
                           ('oversize', b' ' * (u.MAX_MANIFEST_BYTES + 1))):
            path = self.root / label
            path.write_bytes(raw)
            with self.subTest(label=label), self.assertRaises(ValueError):
                u.read_json(path, u.MAX_MANIFEST_BYTES)


if __name__ == '__main__':
    unittest.main()
