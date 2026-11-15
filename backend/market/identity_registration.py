"""Privileged registration of reviewed US Normal Horde evidence; never activates collection."""
import argparse
import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import select
from .db import Session, now
from .ingest import canonical
from .market_configuration import lock_configuration, valid_mapping
from .models import Market, MarketVerification, PlayerMarketMapping, SecurityEvent, User
from .security import aware
from .verification import inspect_mapping

IDENTITY = {'region':'us', 'ruleset':'Normal', 'faction':'Horde', 'house_id':114,
            'source_kind':'auctions', 'transport_ruleset_id':2}


def reviewed_evidence(raw, expected_hash):
    """The operator explicitly binds the reviewed public research, not a success report."""
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError('Reviewed evidence hash mismatch')
    review = json.loads(raw)
    if any(review.get(k) != v for k,v in IDENTITY.items()):
        raise ValueError('Only US Normal Horde house 114 auctions are in scope')
    observed = aware(datetime.fromisoformat(review['observed_at']))
    if not now()-timedelta(days=1) <= observed <= now():
        raise ValueError('Fresh reviewed research required')
    samples = review['independent_observation']['samples']
    for house,ruleset in ((114,'Normal'),(113,'PvP')):
        matching = {s['item_id'] for s in samples if s['house_id']==house and s['ruleset']==ruleset
            and s['region']=='us' and s['faction']=='Horde' and s['matched'] is True
            and s['quantity']==s['api_quantity'] and s['minimum_unit_copper']==s['api_minimum_unit_copper']
            and s['quantity']>0 and s['source_url'].startswith('https://forevermastery.com/en/items/')}
        if len(matching)<4:
            raise ValueError('Four reconciled item observations per Horde market required')
    return review


def register(raw, expected_hash, actor_name, *, factory=Session, client=None, pause=time.sleep):
    review = reviewed_evidence(raw, expected_hash)
    with factory.begin() as db:
        # Same lock order as collection/configuration; the entire registration rolls back on failure.
        lock_configuration(db)
        actor = db.scalar(select(User).where(User.username==actor_name, User.role=='admin', User.active.is_(True)))
        if actor is None:
            raise ValueError('Active administrator identity required')
        existing = db.scalar(select(PlayerMarketMapping).where(PlayerMarketMapping.region=='us',
            PlayerMarketMapping.source_kind=='auctions', PlayerMarketMapping.ruleset=='Normal',
            PlayerMarketMapping.faction=='Horde'))
        if existing is not None:
            raise ValueError('Mapping already registered; inspect existing evidence instead of overwriting it')
        markets = list(db.scalars(select(Market).where(Market.region=='us', Market.house_id==114,
            Market.source_kind=='auctions')))
        if len(markets)>1 or any(m.enabled or m.ruleset_id!=2 for m in markets):
            raise ValueError('Duplicate, enabled or differently routed destination requires review')
        market = markets[0] if markets else Market(region='us', ruleset_id=2, house_id=114,
            source_kind='auctions', label='US — Normal — Horde', interval_seconds=300,
            enabled=False, verified=False)
        db.add(market)
        db.flush()
        # Existing verifier performs fresh authenticated index, identity and normalization checks itself.
        report = inspect_mapping(market, client, pause)
        prior = next(r for r in review['upstream_probes']['responses'] if r['mapping']=={
            'region':'us','transport_ruleset_id':2,'house_id':114,'source_kind':'auctions'})
        if (report['requests'][-1]['sha256'] != prior['sha256']
                or report['requests'][-1]['headers']['Last-Modified'] != prior['headers']['Last-Modified']):
            raise ValueError('Upstream generation changed; reconcile the public observations again')
        encoded = canonical(report)
        receipt = MarketVerification(market_id=market.id, actor_id=actor.id, evidence=encoded,
            evidence_hash=hashlib.sha256(encoded.encode()).hexdigest(),
            notes='Fresh upstream verification for reviewed US Normal Horde 114; disabled pending owner confirmation')
        db.add(receipt)
        db.flush()
        market.verified = True
        evidence = {**IDENTITY, 'review_sha256':expected_hash, 'review':review,
            'upstream_receipt':{'id':receipt.id,'evidence_hash':receipt.evidence_hash},
            'independent_observation':review['independent_observation'],
            'independent_source_url':review['independent_source_url']}
        encoded = canonical(evidence)
        mapping = PlayerMarketMapping(**IDENTITY, confidence='verified', evidence=encoded,
            evidence_hash=hashlib.sha256(encoded.encode()).hexdigest(), verified_at=now())
        if not valid_mapping(mapping):
            raise ValueError('Registry evidence failed validation')
        db.add(mapping)
        db.flush()
        for action,detail in (
            ('market.verified', f'market={market.id} verification={receipt.id} sha256={receipt.evidence_hash}'),
            ('market.identity.registered', f'mapping={mapping.id} market={market.id} sha256={mapping.evidence_hash}; disabled; owner switch confirmation pending')):
            db.add(SecurityEvent(actor_id=actor.id, action=action, detail=detail))
        return {'market_id':market.id, 'mapping_id':mapping.id, 'verification_id':receipt.id,
            'review_sha256':expected_hash, 'mapping_evidence_hash':mapping.evidence_hash,
            'verification_evidence_hash':receipt.evidence_hash, 'registered_at':now().isoformat(),
            'enabled':market.enabled, 'interval_seconds':market.interval_seconds,
            'transition_executed':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--actor', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(register(args.evidence.read_bytes(), args.expected_sha256, args.actor)))
    except Exception:
        parser.exit(1, 'Registration failed; transaction rolled back; no collection switch performed.\n')


if __name__=='__main__':
    main()
