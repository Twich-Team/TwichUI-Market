"""Two read-only provider requests for isolated ingestion-capacity verification.

Emit a bounded gzip tar to stdout; never ingest or change production settings.
Run using the existing worker credential environment and redirect to an ignored
private artifact. Do not commit the captured listing bodies.
"""
import io
import json
import sys
import tarfile
from types import SimpleNamespace
from market.worker import BlizzardClient


def main():
    client = BlizzardClient()
    receipts = []
    with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
        for kind in ('auctions', 'commodities'):
            metadata, body = client.fetch(SimpleNamespace(region='us', ruleset_id=2, house_id=114,
                source_kind=kind, etag=None, last_modified=None))
            if metadata['status'] != 200 or metadata['headers'].get('Battlenet-Namespace') != 'dynamic-forever-us':
                raise ValueError('Capture stopped')
            info = tarfile.TarInfo(kind+'.json')
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
            receipts.append({'source_kind': kind, **metadata})
        body = json.dumps(receipts).encode()
        info = tarfile.TarInfo('receipt.json')
        info.size = len(body)
        archive.addfile(info, io.BytesIO(body))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Bounded capture failed; no production ingestion/configuration writes.') from None
