"""Operator-only extension of verified market 2; never trusts supplied live success.

Dry-run performs four bounded authenticated requests. --apply registers those
fresh proofs after all release gates; it creates no extra market or observation.
"""
import argparse
import hashlib
import json
import time
from types import SimpleNamespace
from sqlalchemy import select
from .db import Session, now
from .feed_collection import KINDS, verified_identity
from .ingest import canonical, normalize
from .market_configuration import lock_configuration, mapping_for
from .models import Market, MarketFeed, User
from .security import audit
from .verification import inspect_mapping
from .worker import BlizzardClient

EXPECTED = dict(region='us', ruleset_id=2, house_id=114, source_kind='auctions')


def configure(actor_id, *, apply=False, factory=Session, client=None, pause=time.sleep):
    client = client or BlizzardClient()
    with factory.begin() as db:
        lock_configuration(db)
        actor = db.get(User, actor_id)
        if actor is None or not actor.active or actor.role != 'admin':
            raise ValueError('Active administrator required')
        market = db.scalar(select(Market).where(Market.id == 2).with_for_update())
        if market is None or any(getattr(market, key) != value for key, value in EXPECTED.items()):
            raise ValueError('Only the existing US ruleset-2 house-114 auction market can be extended')
        if not market.enabled or not market.verified or market.interval_seconds != 300:
            raise ValueError('Existing verified 300-second collector required')
        mapping = mapping_for(db, market)
        if mapping is None or mapping.ruleset != 'Normal' or mapping.faction != 'Horde' or mapping.transport_ruleset_id != 2:
            raise ValueError('Verified Normal/Horde player mapping required')
        if db.scalar(select(Market.id).where(Market.enabled.is_(True), Market.id != 2).limit(1)):
            raise ValueError('Another market is collecting; refusing campaign expansion')
        feeds = list(db.scalars(select(MarketFeed).where(MarketFeed.market_id == 2).order_by(MarketFeed.source_kind)))
        if market.unified_coverage:
            if [f.source_kind for f in feeds if f.enabled] != list(KINDS):
                raise ValueError('Incomplete existing feed configuration; inspect before changing')
            for feed in feeds: verified_identity(market, feed)
            return {'market_id':2, 'status':'already_configured', 'provider_requests':0}
        if feeds:
            raise ValueError('Unactivated feed configuration exists; inspect before changing')
        # Existing verifier checks the ruleset index, house index, identity,
        # namespace and complete ordinary-auction normalization: three requests.
        regular = inspect_mapping(market, client, pause)
        if regular['house_name'] != 'Horde Auction House':
            raise ValueError('Unexpected house identity')
        transport = SimpleNamespace(**{**EXPECTED, 'source_kind':'commodities'}, etag=None, last_modified=None)
        metadata, body = client.fetch(transport)
        if metadata['status'] != 200 or metadata['headers'].get('Battlenet-Namespace') != 'dynamic-forever-us':
            raise ValueError('Fresh authenticated commodity source required')
        payload = json.loads(body)
        expected_link = 'https://us.api.blizzard.com/data/wow/ruleset/2/auctions/114/commodities?namespace=dynamic-forever-us'
        if payload.get('_links', {}).get('self', {}).get('href') != expected_link:
            raise ValueError('Commodity source does not identify this exact house and namespace')
        rows = normalize(payload, 'commodities')
        if not rows or any(json.loads(r['variant']) != {'id':r['item_id']} for r in rows):
            raise ValueError('Nonempty verified commodity identity contract required')
        commodity = {'mapping':{**EXPECTED, 'source_kind':'commodities'}, 'verified_at':now().isoformat(),
            'namespace':'dynamic-forever-us', 'listing_count':len(rows), 'response':metadata,
            'normalized_sha256':hashlib.sha256(canonical(rows).encode()).hexdigest()}
        proofs = []
        for kind, report in zip(KINDS, (regular, commodity)):
            proof = {'identity':{**EXPECTED, 'source_kind':kind, 'namespace':'dynamic-forever-us', 'scope':'ruleset_house'},
                'actor_id':actor.id, 'verified_at':now().isoformat(), 'report':report,
                'evidence_sha256':hashlib.sha256(canonical(report).encode()).hexdigest(),
                'registry_evidence_sha256':mapping.evidence_hash}
            proofs.append(proof)
            if apply: db.add(MarketFeed(market_id=2, source_kind=kind, enabled=True, verification=canonical(proof)))
        if apply:
            market.unified_coverage = True
            # Keep the already established next check and 300-second cadence.
            audit(db, actor.id, 'market.feeds.activated', 'market=2 house=114 interval=300 '+
                ' '.join(p['identity']['source_kind']+'='+p['evidence_sha256'] for p in proofs))
        return {'market_id':2, 'status':'activated' if apply else 'verified_dry_run', 'provider_requests':4,
                'mapping_unchanged':True, 'interval_seconds':300, 'proofs':proofs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actor-id', type=int, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try: print(json.dumps(configure(args.actor_id, apply=args.apply), indent=2))
    except Exception: parser.exit(1, 'Feed verification/activation refused; no configuration changes committed.\n')


if __name__ == '__main__': main()
