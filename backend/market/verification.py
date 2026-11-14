"""Operator-only live mapping verification. Never accepts a supplied success report."""
import argparse
import hashlib
import json
import time
from urllib.parse import urlencode
from sqlalchemy import select
from .db import Session, now
from .ingest import canonical, normalize
from .models import Market, MarketVerification, SecurityEvent, User
from .probe import REGIONS, summarize
from .worker import BlizzardClient


def inspect_mapping(market,client=None,pause=time.sleep):
    if market.region not in REGIONS or market.source_kind not in ('auctions','commodities') or market.ruleset_id<=0 or market.house_id<=0:
        raise ValueError('Invalid market mapping')
    client=client or BlizzardClient()
    evidence=[]
    def fetch(path):
        url=f'https://{market.region}.api.blizzard.com{path}?'+urlencode({
            'namespace':f'dynamic-forever-{market.region}','locale':'en_US'})
        meta,body=client.transport(url,token=client.authenticate())
        client.throttle(meta)
        if meta['status']!=200 or meta['headers'].get('Battlenet-Namespace')!=f'dynamic-forever-{market.region}':
            raise ValueError('Live verification requires HTTP 200 and matching upstream namespace')
        data=json.loads(body)
        evidence.append({**meta,'structure':summarize(body)})
        pause(1)
        return data,body
    rulesets,_=fetch('/data/wow/ruleset/index')
    if not any(r.get('id')==market.ruleset_id for r in rulesets.get('rulesets',[])):
        raise ValueError('Ruleset absent from live index')
    houses,_=fetch(f'/data/wow/ruleset/{market.ruleset_id}/auctions/')
    house=next((h for h in houses.get('auctions',[]) if h.get('id')==market.house_id),None)
    if house is None:raise ValueError('Auction house absent from live index')
    parent,body=fetch(f'/data/wow/ruleset/{market.ruleset_id}/auctions/{market.house_id}')
    if parent.get('id')!=market.house_id or parent.get('name')!=house.get('name'):
        raise ValueError('House identity disagrees with live index')
    del parent
    if market.source_kind=='commodities':
        commodity,body=fetch(f'/data/wow/ruleset/{market.ruleset_id}/auctions/{market.house_id}/commodities')
        del commodity
    rows=normalize(json.loads(body),market.source_kind)
    if not rows:raise ValueError('Initial verification requires observed nonempty listings')
    return {'version':1,'verified_at':now().isoformat(),
            'mapping':{k:getattr(market,k) for k in ('region','ruleset_id','house_id','source_kind')},
            'house_name':house['name'],'scope':'Verified upstream house feed; ruleset URL alone does not establish an independent in-game economy.',
            'listing_count':len(rows),'normalized_sha256':hashlib.sha256(canonical(rows).encode()).hexdigest(),
            'requests':evidence}


def verify_market(market_id,actor_name,notes,*,factory=Session,client=None,pause=time.sleep):
    if not notes.strip() or len(notes)>2000:raise ValueError('Verification notes required (maximum 2000 characters)')
    with factory.begin() as db:
        actor=db.scalar(select(User).where(User.username==actor_name,User.active.is_(True),User.role=='admin'))
        if actor is None:raise ValueError('Active administrator identity required')
        market=db.scalar(select(Market).where(Market.id==market_id).with_for_update())
        if market is None or market.enabled:raise ValueError('Existing disabled market required')
        report=inspect_mapping(market,client,pause)
        encoded=canonical(report)
        record=MarketVerification(market_id=market.id,actor_id=actor.id,evidence=encoded,
            evidence_hash=hashlib.sha256(encoded.encode()).hexdigest(),notes=notes)
        db.add(record);db.flush()
        market.verified=True
        db.add(SecurityEvent(actor_id=actor.id,action='market.verified',detail=f'market={market.id} verification={record.id} sha256={record.evidence_hash}'))
        return {'market_id':market.id,'verification_id':record.id,'evidence_hash':record.evidence_hash,'report':report}


def enable_initial(market_id,actor_name,notes,*,factory=Session):
    from datetime import timedelta
    from .security import aware
    if not notes.strip() or len(notes)>2000:raise ValueError('Activation notes required')
    with factory.begin() as db:
        actor=db.scalar(select(User).where(User.username==actor_name,User.active.is_(True),User.role=='admin'))
        market=db.scalar(select(Market).where(Market.id==market_id).with_for_update())
        if actor is None or market is None or not market.verified:raise ValueError('Verified mapping and active administrator required')
        expected={'region':'us','ruleset_id':2,'house_id':110,'source_kind':'auctions'}
        if any(getattr(market,k)!=v for k,v in expected.items()):raise ValueError('Only initial US house 110 feed may be activated by this command')
        if db.scalar(select(Market.id).where(Market.enabled.is_(True),Market.id!=market_id).limit(1)):
            raise ValueError('Another market is already enabled; refusing expansion')
        record=db.scalar(select(MarketVerification).where(MarketVerification.market_id==market_id).order_by(MarketVerification.id.desc()).limit(1))
        if record is None or aware(record.created_at)<now()-timedelta(days=1):raise ValueError('Fresh live verification receipt required')
        if hashlib.sha256(record.evidence.encode()).hexdigest()!=record.evidence_hash or json.loads(record.evidence)['mapping']!=expected:
            raise ValueError('Verification evidence integrity or identity mismatch')
        market.enabled=True
        market.interval_seconds=300
        market.next_check=now()
        db.add(SecurityEvent(actor_id=actor.id,action='market.schedule.updated',detail=f'market={market.id} verification={record.id} interval=300 initial_activation; {notes}'[:200]))
        return {'market_id':market.id,'enabled':True,'verification_id':record.id,'interval_seconds':300}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--market',type=int,required=True)
    parser.add_argument('--actor',required=True)
    parser.add_argument('--notes',required=True)
    parser.add_argument('--enable-initial',action='store_true',help='Separate guarded activation of only the verified initial US house 110 feed')
    args=parser.parse_args()
    try:
        print(json.dumps((enable_initial if args.enable_initial else verify_market)(args.market,args.actor,args.notes)))
    except Exception:
        parser.exit(1,'Live verification failed; no mapping enabled or newly verified. Inspect upstream status with bounded probes.\n')


if __name__=='__main__':main()
