"""Inactive U1 broad-summary exporter. No database, HTTP, addon or scheduler hooks.

Input is an ordered stream of exact identities with already-derived canonical
current evidence, pinned to one source observation. Never calculates prices.
"""
from bisect import bisect_left
from contextlib import ExitStack
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import tempfile

import jsonschema
from referencing import Registry, Resource

# Reuse the experimental tuple vocabulary and frozen canonical serializer.
from advisor_index_feasibility import COLUMNS, STATES, canonical

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / 'contracts/market-summary-index-proposal'
SCHEMA = json.loads((PROPOSAL / 'u1/manifest.schema.json').read_bytes())
OLD_SCHEMA = json.loads((PROPOSAL / 'schema.json').read_bytes())
REGISTRY = Registry().with_resources([
    (s['$id'], Resource.from_contents(s)) for s in (SCHEMA, OLD_SCHEMA)
])
VALIDATOR = jsonschema.Draft202012Validator(
    SCHEMA, registry=REGISTRY, format_checker=jsonschema.FormatChecker())
ROW_VALIDATOR = jsonschema.Draft202012Validator(OLD_SCHEMA['properties']['records']['items'])
BUCKETS = 64
MAX_PART_BYTES = 256 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_RECORDS = 150_000
MAX_COPPER = 99_999_999_999  # Existing canonical pricing support; never widen it.


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp requires a timezone')
    return parsed


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Integer outside supported range')
    return value


def identity(item, variant):
    integer(item, 1, 2**31 - 1)
    if type(variant) is not str or re.fullmatch('[0-9a-f]{64}', variant) is None:
        raise ValueError('Variant identity requires exactly 64 lowercase hexadecimal characters')


def age(metadata):
    delta = (timestamp(metadata['generated_at']) -
             timestamp(metadata['source_observation']['observed_at'])).total_seconds()
    if delta < 0 or delta > 2**31 - 1:
        raise ValueError('Source observation age outside supported range')
    return int(delta)


def validate_metadata(metadata):
    candidate = dict(metadata, partitioning={'algorithm': 'item_id_modulo', 'buckets': BUCKETS,
                     'max_partition_bytes': MAX_PART_BYTES}, partitions=[], record_count=0,
                     generation_id='0' * 64)
    VALIDATOR.validate(candidate)
    age(metadata)
    market = metadata['market']
    if market['mapping_verified'] and (market['player_ruleset'] is None or
                                       market['mapping_evidence_sha256'] is None):
        raise ValueError('Verified mapping requires ruleset and evidence')
    evidence = market['mapping_evidence_sha256']
    if evidence is not None and re.fullmatch('[0-9a-f]{64}', evidence) is None:
        raise ValueError('Mapping evidence requires an exact SHA-256')
    if int(metadata['source_observation']['observation_id']) > int(metadata['source_watermark']):
        raise ValueError('Source observation exceeds pinned watermark')


def validate_row(row, metadata):
    ROW_VALIDATOR.validate(row)
    identity(row[0], row[1])
    for i, maximum in ((2, 4), (7, 2**31 - 1), (8, 1)):
        integer(row[i], 0, maximum)
    if row[6] is not None:
        integer(row[6], 0, 2**53 - 1)
    state = STATES[row[2]]
    if row[7] != age(metadata):
        raise ValueError('Row age must match pinned source observation')
    prices = row[3:6]
    for price in prices:
        if price is not None and (re.fullmatch('[1-9][0-9]{0,10}', price) is None or int(price) > MAX_COPPER):
            raise ValueError('Noncanonical or unsupported copper')
    if state == 'priced':
        if not any(p is not None for p in prices) or row[6] is None or row[6] <= 0 or row[8] != 0:
            raise ValueError('Priced evidence requires a metric, positive supply and limited confidence')
    elif prices != [None] * 3:
        raise ValueError('Non-priced state cannot carry prices')
    if state == 'supply_only' and (row[6] is None or row[6] <= 0 or row[8] != 1):
        raise ValueError('Supply-only evidence requires positive supply and unavailable price confidence')
    if state == 'absent' and (row[6] != 0 or row[8] != 1 or
                              not metadata['source_observation']['scope_complete']):
        raise ValueError('Absence requires complete source observation and zero supply')
    if state in ('unknown', 'unsupported') and (row[6] is not None or row[8] != 1):
        raise ValueError('Unknown/unsupported evidence must remain unavailable')
    if state in ('priced', 'supply_only') and not metadata['source_observation']['scope_complete']:
        raise ValueError('Incomplete source cannot provide supported summary evidence')


def project_record(record, metadata):
    """Project bridge-like current evidence; detailed history is never required.

    Caller pins the stream to metadata's observation/watermark. Missing current
    evidence is unknown, never absence. No descriptor/name matching is attempted.
    """
    if record['observation_id'] != metadata['source_observation']['observation_id']:
        raise ValueError('Record belongs to a different source observation')
    item, variant = record['item_id'], record['variant_key']
    identity(item, variant)
    current = record.get('current')
    prices, supply, confidence, state = [None] * 3, None, 1, 'unknown'
    if current is not None:
        if current['algorithm'] != metadata['pricing_algorithm']:
            raise ValueError('Mixed pricing algorithm')
        if type(current['complete']) is not bool:
            raise ValueError('Current completeness must be explicit')
        source_state = current['state']
        if source_state not in ('listed', 'absent', 'unknown', 'unsupported'):
            raise ValueError('Unsupported current state')
        if (current['complete'] and metadata['source_observation']['scope_complete']):
            if source_state == 'absent':
                integer(current['supply'], 0, 0)
                state, supply = 'absent', 0
            elif source_state == 'unsupported' or current.get('arithmetic_status') == 'unsupported':
                state = 'unsupported'
            elif source_state == 'listed':
                if current['arithmetic_status'] != 'exact':
                    raise ValueError('Missing exact arithmetic evidence')
                metrics = current['metrics']
                prices = [metrics[k] for k in ('recent_copper', 'market_value_copper', 'minimum_copper')]
                supply = integer(current['supply'], 1, 2**53 - 1)
                state = 'priced' if any(p is not None for p in prices) else 'supply_only'
                confidence = 0 if state == 'priced' else 1
    row = [item, variant, STATES.index(state), *prices, supply, age(metadata), confidence]
    validate_row(row, metadata)
    return row


def write_index(records, metadata, destination, *, max_partition_bytes=MAX_PART_BYTES):
    """Single pass; O(64 buffers + one record), with bounded disposable disk spools.

    Requires strict (item_id, variant_key) ordering; duplicate/unsorted input fails.
    Publishes only a complete new directory. Never replaces an existing generation.
    """
    validate_metadata(metadata)
    integer(max_partition_bytes, 128, MAX_PART_BYTES)
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('Use a new disposable generation destination')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.u1-stage-', dir=destination.parent) as temp:
        stage = Path(temp) / 'generation'
        stage.mkdir()
        counts, sizes, prior, total = {}, {}, None, 0
        with ExitStack() as stack:
            files = {}
            for record in records:
                row = project_record(record, metadata)
                key = tuple(row[:2])
                if prior is not None and key <= prior:
                    raise ValueError('Input must be unique and ordered by (item_id, variant_key)')
                prior = key
                total += 1
                if total > MAX_RECORDS:
                    raise ValueError('Summary record limit exceeded; no variants were published')
                bucket = row[0] % BUCKETS
                raw = canonical(row)
                new_size = sizes.get(bucket, 2) + len(raw) + (1 if bucket in files else 0)
                if new_size > max_partition_bytes:
                    raise ValueError(f'Bucket {bucket} exceeds {max_partition_bytes} bytes at item {row[0]}; '
                                     'no variants published. Use a separately reviewed deterministic '
                                     'subdivision before retrying; never raise the hard cap or prune variants.')
                if bucket not in files:
                    files[bucket] = stack.enter_context((stage / f'{bucket}.tmp').open('wb'))
                    files[bucket].write(b'[')
                else:
                    files[bucket].write(b',')
                files[bucket].write(raw)
                sizes[bucket] = new_size
                counts[bucket] = counts.get(bucket, 0) + 1
            for file in files.values():
                file.write(b']')
        parts = []
        for bucket in sorted(counts):
            path = stage / f'{bucket}.tmp'
            # Each partition is hard bounded; never materialize the whole market.
            raw = path.read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            filename = f'{bucket:02d}-{sha}.json'
            path.rename(stage / filename)
            parts.append({'bucket': bucket, 'file': filename, 'bytes': len(raw),
                          'record_count': counts[bucket], 'sha256': sha})
            del raw
        manifest = dict(metadata, partitioning={'algorithm': 'item_id_modulo', 'buckets': BUCKETS,
                        'max_partition_bytes': max_partition_bytes},
                        partitions=parts, record_count=total)
        manifest['generation_id'] = digest(manifest)
        raw = canonical(manifest)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise ValueError('Manifest byte limit')
        VALIDATOR.validate(manifest)
        (stage / 'manifest.json').write_bytes(raw)
        stage.rename(destination)
    return manifest


def read_json(path, limit):
    # Bound the actual read, including files that grow after stat().
    with Path(path).open('rb') as file:
        raw = file.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('File byte limit')
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('Duplicate JSON key')
            out[key] = value
        return out
    try:
        value = json.loads(raw, object_pairs_hook=unique)
        if raw != canonical(value):
            raise ValueError('Noncanonical JSON')
    except (RecursionError, UnicodeError) as error:
        raise ValueError('Malformed bounded JSON') from error
    return raw, value


def read_manifest(directory, *, expected_generation_id):
    """Require a caller-pinned identity. Hashes detect corruption, not authenticity."""
    _, manifest = read_json(Path(directory) / 'manifest.json', MAX_MANIFEST_BYTES)
    VALIDATOR.validate(manifest)
    metadata = {k: v for k, v in manifest.items() if k not in
                ('generation_id', 'partitioning', 'partitions', 'record_count')}
    validate_metadata(metadata)
    if manifest['generation_id'] != expected_generation_id or digest(
            {k: v for k, v in manifest.items() if k != 'generation_id'}) != expected_generation_id:
        raise ValueError('Manifest integrity or pinned generation mismatch')
    previous, count = -1, 0
    for part in manifest['partitions']:
        bucket = part['bucket']
        if bucket <= previous or part['file'] != f"{bucket:02d}-{part['sha256']}.json":
            raise ValueError('Partition ordering, duplicate bucket or unsafe filename')
        if part['bytes'] > manifest['partitioning']['max_partition_bytes']:
            raise ValueError('Partition exceeds declared byte bound')
        previous = bucket
        count += part['record_count']
    if count != manifest['record_count']:
        raise ValueError('Manifest record count mismatch')
    return manifest


def read_partition(directory, manifest, part):
    raw, rows = read_json(Path(directory) / part['file'], manifest['partitioning']['max_partition_bytes'])
    if len(raw) != part['bytes'] or hashlib.sha256(raw).hexdigest() != part['sha256']:
        raise ValueError('Partition integrity')
    if type(rows) is not list or len(rows) != part['record_count']:
        raise ValueError('Partition count')
    prior = None
    for row in rows:
        validate_row(row, manifest)
        key = tuple(row[:2])
        if row[0] % BUCKETS != part['bucket'] or (prior is not None and key <= prior):
            raise ValueError('Partition routing/order/duplicate identity')
        prior = key
    return rows


class Index:
    """Offline reference reader: validate manifest, read only one bounded part.

    Keeps at most one decoded partition. Native Lua allocation/slicing is future work.
    """
    def __init__(self, directory, *, expected_generation_id):
        self.directory = Path(directory)
        self.manifest = read_manifest(directory, expected_generation_id=expected_generation_id)
        self.parts = {p['bucket']: p for p in self.manifest['partitions']}
        self.cached_bucket, self.rows, self.keys = None, [], []

    def lookup(self, item, variant):
        identity(item, variant)
        bucket = item % BUCKETS
        part = self.parts.get(bucket)
        if part is None:
            return {'state': 'unavailable', 'row': None}
        if self.cached_bucket != bucket:
            self.cached_bucket, self.rows, self.keys = None, [], []
            rows = read_partition(self.directory, self.manifest, part)
            self.rows = rows
            self.keys = [tuple(r[:2]) for r in rows]
            self.cached_bucket = bucket
        pos = bisect_left(self.keys, (item, variant))
        if pos == len(self.rows) or self.keys[pos] != (item, variant):
            return {'state': 'unavailable', 'row': None}
        row = self.rows[pos]
        return {'state': STATES[row[2]], 'row': row.copy()}

    def verify_all(self):
        # Streaming across partitions; does not retain the complete market.
        for part in self.manifest['partitions']:
            read_partition(self.directory, self.manifest, part)
        return True
