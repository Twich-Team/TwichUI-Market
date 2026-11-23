"""Opt-in integrity sidecar for immutable Contract 3 current prices.

No price calculation, history projection, database migration or Lua execution.
The source generation authenticates the exact original thirteen-column tuples.
"""
import hashlib
import json

from . import workshop_summary as summary

FORMAT = 'twichui-workshop-prepared-current'
VERSION = 1
WIDTH = 135
COUNTS = (16, 32)
MAX_PART_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
HASH = 'sha256-canonical-13-v1'
WIDTHS = (8, 64, 1, 10, 10, 10, 14, 1, 1, 10, 2, 2, 2)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tree(rows):
    """Heap order, root at offset zero; hashes are lowercase ASCII hex words."""
    size = 1 << (max(1, len(rows)) - 1).bit_length()
    nodes = [''] * (2 * size)
    for i in range(size):
        nodes[size + i] = sha(b'row\0' + summary.canonical(rows[i])) if i < len(rows) else sha(b'empty\0')
    for i in range(size - 1, 0, -1):
        nodes[i] = sha(b'node\0' + nodes[2 * i].encode('ascii') + nodes[2 * i + 1].encode('ascii'))
    return nodes[1:]


def fixed(rows):
    """Reference encoder/vector oracle. The Companion has an independent encoder."""
    words = []
    for row in rows:
        summary.validate_row(row)
        for i, (value, width) in enumerate(zip(row, WIDTHS)):
            if value is None:
                word = 'z' * width
            elif i == 1:
                word = value
            else:
                word = format(int(value), f'0{width}x')
            summary.need(len(word) == width, 'prepared field width')
            words.append(word)
    return ''.join(words)


def prepare(manifest, parts, count=16):
    """Validate authoritative source bytes before regrouping exact identities.

    Empty buckets are explicit. Positional leaf proofs plus adjacent authenticated
    positions prove nonmembership; a missing row never establishes observed zero.
    """
    summary.need(type(count) is int and count in COUNTS, 'prepared layout')
    summary.manifest_validator(3).validate(manifest)
    body = {k: v for k, v in manifest.items() if k != 'generation_id'}
    summary.need(summary.digest(body) == manifest['generation_id'], 'prepared source digest')
    groups = [[] for _ in range(count)]
    delivered, previous_bucket, source_bytes = 0, -1, 0
    for descriptor in manifest['partitions']:
        bucket = descriptor['bucket']
        summary.need(bucket > previous_bucket, 'prepared source bucket order')
        previous_bucket = bucket
        raw = parts.get(bucket)
        if type(raw) is str:
            raw = raw.encode('utf-8')
        summary.need(type(raw) is bytes and len(raw) == descriptor['bytes']
                     and sha(raw) == descriptor['sha256'], 'prepared source integrity')
        rows = json.loads(raw)
        summary.need(summary.canonical(rows) == raw and len(rows) == descriptor['record_count'], 'prepared source canonical/count')
        previous = None
        for row in rows:
            summary.validate_row(row, bucket)
            key = (row[0], row[1])
            summary.need(previous is None or previous < key, 'prepared source order')
            previous = key
            groups[row[0] % count].append(row)
        delivered += len(rows)
        source_bytes += len(raw)
    summary.need(delivered == manifest['record_count'], 'prepared source completeness')
    summary.need(source_bytes <= manifest['partitioning']['max_total_bytes']
                 and manifest['coverage']['source_records'] == delivered
                 and manifest['coverage']['delivered_records'] == delivered, 'prepared source coverage')
    descriptors, payloads, total = [], {}, 0
    for bucket, rows in enumerate(groups):
        rows.sort(key=lambda row: (row[0], row[1]))
        nodes = tree(rows)
        data, proofs = fixed(rows), ''.join(nodes)
        size = len(data) + len(proofs)
        total += size
        summary.need(size <= MAX_PART_BYTES and total <= MAX_TOTAL_BYTES, 'prepared generation bound')
        descriptors.append(dict(bucket=bucket, record_count=len(rows), bytes=len(summary.canonical(rows)),
                                sha256=sha(summary.canonical(rows)), merkle_root=nodes[0]))
        payloads[bucket] = (data, proofs)
    result = dict(format=FORMAT, version=VERSION, source_generation_id=manifest['generation_id'],
                  partitions_count=count, record_width=WIDTH, hash_algorithm=HASH,
                  record_count=delivered, partitions=descriptors)
    result['attestation_id'] = summary.digest(result)
    summary.need(len(summary.canonical(result)) <= summary.MAX_MANIFEST, 'prepared attestation bound')
    return result, payloads
