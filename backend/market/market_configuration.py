"""Player-facing identity registry. No inferred ruleset/house correspondence."""
import hashlib
import json
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from .db import now, session
from .models import Market, MarketVerification, PlayerMarketMapping, User
from .security import admin, audit, aware

router=APIRouter(prefix='/api/v1/admin')
REGIONS=('us','eu','kr','tw')
RULESETS=('Normal','PvP','Roleplay','Roleplay PvP')
FACTIONS=('Horde','Alliance','Blackwater')


def valid_mapping(row):
    if row is None or row.confidence!='verified':return False
    try:
        evidence=json.loads(row.evidence)
        return (hashlib.sha256(row.evidence.encode()).hexdigest()==row.evidence_hash
            and evidence['region']==row.region and evidence['house_id']==row.house_id
            and evidence['ruleset']==row.ruleset and evidence['faction']==row.faction
            and evidence['upstream_receipt'] and evidence['independent_observation']
            and evidence['independent_source_url'].startswith('https://'))
    except (ValueError,KeyError,TypeError):return False


def mapping_for(db,market):
    row=db.scalar(select(PlayerMarketMapping).where(PlayerMarketMapping.region==market.region,
        PlayerMarketMapping.house_id==market.house_id,PlayerMarketMapping.source_kind==market.source_kind))
    return row if valid_mapping(row) else None


def activation_guard(db,market,*,replacing=None):
    if not market.verified or not mapping_for(db,market):
        raise HTTPException(409,'Verified player-facing ruleset/faction mapping and live feed receipt are required')
    record=db.scalar(select(MarketVerification).where(MarketVerification.market_id==market.id).order_by(MarketVerification.id.desc()).limit(1))
    expected={key:getattr(market,key) for key in ('region','ruleset_id','house_id','source_kind')}
    try:
        good=(record is not None and aware(record.created_at)>=now()-timedelta(days=1)
            and hashlib.sha256(record.evidence.encode()).hexdigest()==record.evidence_hash
            and json.loads(record.evidence)['mapping']==expected)
    except (ValueError,KeyError,TypeError):good=False
    if not good:raise HTTPException(409,'Fresh intact live verification receipt required')
    if db.scalar(select(Market.id).where(Market.enabled.is_(True),Market.id!=market.id,Market.id!=(replacing or -1)).limit(1)):
        raise HTTPException(409,'Another market is collecting. Use a confirmed single-market transition')


def lock_configuration(db):
    if db.bind.dialect.name=='postgresql':
        # Lock order matches ingestion and prevents concurrent activations on distinct rows.
        db.execute(text('SELECT pg_advisory_xact_lock(7140232)'))
        db.execute(text('SELECT pg_advisory_xact_lock(7140237)'))


@router.get('/market-options')
def options(user:User=Depends(admin),db:Session=Depends(session)):
    mappings=list(db.scalars(select(PlayerMarketMapping)))
    return {'regions':list(REGIONS),'rulesets':list(RULESETS),'factions':list(FACTIONS),
        'choices':[{'region':region,'ruleset':ruleset,'faction':faction,
            'available':any(valid_mapping(m) and (m.region,m.ruleset,m.faction)==(region,ruleset,faction) for m in mappings)}
            for region in REGIONS for ruleset in RULESETS for faction in FACTIONS],
        'notice':'Unverified player-facing identities cannot start collection. A ruleset URL is only a transport alias; it does not identify the economy.'}


class GuidedMarket(BaseModel):
    region:Literal['us','eu','kr','tw']
    ruleset:Literal['Normal','PvP','Roleplay','Roleplay PvP']
    faction:Literal['Horde','Alliance','Blackwater']
    interval_seconds:int=Field(default=300,ge=300,le=86400)
    enabled:bool=False


@router.post('/configured-markets',status_code=201)
def create(body:GuidedMarket,user:User=Depends(admin),db:Session=Depends(session)):
    from .market_api import market_view
    lock_configuration(db)
    mapping=db.scalar(select(PlayerMarketMapping).where(PlayerMarketMapping.region==body.region,
        PlayerMarketMapping.ruleset==body.ruleset,PlayerMarketMapping.faction==body.faction,
        PlayerMarketMapping.source_kind=='auctions'))
    if not valid_mapping(mapping):raise HTTPException(409,'Player-facing identity is unresolved; no feed was created or enabled')
    if db.scalar(select(Market.id).where(Market.region==body.region,Market.house_id==mapping.house_id,Market.source_kind=='auctions').limit(1)):
        raise HTTPException(409,'This feed is already configured, including any API aliases')
    if body.enabled:raise HTTPException(409,'Create disabled, obtain a fresh live receipt, then confirm the market transition')
    row=Market(region=body.region,ruleset_id=mapping.transport_ruleset_id,house_id=mapping.house_id,source_kind='auctions',
        label=f'{body.region.upper()} — {body.ruleset} — {body.faction}',interval_seconds=body.interval_seconds,enabled=False,verified=False)
    db.add(row);audit(db,user.id,'market.created.guided');db.commit()
    return market_view(row,player_identity=True)


@router.get('/markets/{market_id}/diagnostics')
def diagnostics(market_id:int,user:User=Depends(admin),db:Session=Depends(session)):
    from .market_api import require_market,verifications
    market=require_market(db,market_id);mapping=mapping_for(db,market)
    from .feed_collection import feed_health
    return {'feeds': feed_health(db, market), 'region':market.region,'transport_ruleset_id':market.ruleset_id,'house_id':market.house_id,
        'namespace':f'dynamic-forever-{market.region}','source_kind':market.source_kind,
        'player_identity':{'ruleset':mapping.ruleset,'faction':mapping.faction,'confidence':mapping.confidence,
            'verified_at':mapping.verified_at,'evidence':json.loads(mapping.evidence),'evidence_hash':mapping.evidence_hash} if mapping else None,
        'verification_receipts':verifications(market_id,user,db),
        'notice':'Upstream feed verification is separate from player-facing identity verification.'}


class Transition(BaseModel):
    from_market_id:int=Field(ge=1)
    to_market_id:int=Field(ge=1)
    confirm:bool


@router.post('/market-transition')
def transition(body:Transition,user:User=Depends(admin),db:Session=Depends(session)):
    from .market_api import require_market,market_view
    if not body.confirm or body.from_market_id==body.to_market_id:raise HTTPException(409,'Explicit confirmation of two distinct markets is required')
    lock_configuration(db)
    old=require_market(db,body.from_market_id);new=require_market(db,body.to_market_id)
    if not old.enabled or new.enabled:raise HTTPException(409,'Transition requires one currently collecting market and a disabled destination')
    activation_guard(db,new,replacing=old.id)
    old.enabled=False;new.enabled=True;new.next_check=now()
    audit(db,user.id,'market.transition.confirmed',f'from={old.id} to={new.id}; previous schedule disabled; all history preserved')
    db.commit()
    return {'previous':market_view(old),'selected':market_view(new),'history_preserved':True}
