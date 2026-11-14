"""Private research and collection administration endpoints."""
import json
import os
from pathlib import Path as FilePath
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import now, session
from .models import CollectionRun, Listing, Market, Observation, Snapshot, User
from .pricing import daily_history, values
from .security import admin, audit, aware, identity

router = APIRouter(prefix='/api/v1')
MarketId = Annotated[int,Path(ge=1,le=2**31-1)]
MONEY_KEYS = {'recent_price','lowest_buyout','market_value','historical_value','buyout','unit_price','bid','total_buyout'}
BACKUP_DIRECTORY = FilePath('/backup-status')


def backup_state():
    status = {'status':'not_configured','last_restoration_verified_at':None}
    try:
        path=BACKUP_DIRECTORY/'status.json'
        if path.is_file() and path.stat().st_size<16384:
            data=json.loads(path.read_text())
            status.update({key:data[key] for key in ('status','last_success','checked_at','bytes','keep','error','last_restoration_verified_at') if key in data})
    except (OSError,ValueError,TypeError):
        status['status']='unavailable'
    return status


def money_contract(value):
    if isinstance(value, list):
        return [money_contract(row) for row in value]
    if isinstance(value, dict):
        return {key: (str(item) if item is not None and key in MONEY_KEYS else money_contract(item)) for key,item in value.items()}
    return value


def market_view(market):
    checked_age = max(0, int((now()-aware(market.last_success)).total_seconds())) if market.last_success else None
    try:
        modified = aware(parsedate_to_datetime(market.last_modified)) if market.last_modified else None
    except (TypeError, ValueError, OverflowError):
        modified = None
    source_age = max(0,int((now()-modified).total_seconds())) if modified else None
    return {'id':market.id,'region':market.region,'ruleset_id':market.ruleset_id,'house_id':market.house_id,
            'source_kind':market.source_kind,'label':market.label,'enabled':market.enabled,'verified':market.verified,
            'interval_seconds':market.interval_seconds,'last_success':market.last_success,'next_check':market.next_check,
            'last_modified':market.last_modified,'check_age_seconds':checked_age,'source_age_seconds':source_age,
            'freshness': 'unknown' if source_age is None else ('stale' if source_age > max(3600,market.interval_seconds*2) else 'current'),
            'failures':market.failures,'last_error':market.last_error}


def require_market(db, market_id):
    market = db.get(Market,market_id)
    if not market:
        raise HTTPException(404,'Market not found')
    return market


def latest_observation(db, market_id):
    return db.scalar(select(Observation).where(Observation.market_id == market_id)
        .order_by(Observation.retrieved_at.desc(),Observation.id.desc()).limit(1))


@router.get('/markets')
def markets(user: User = Depends(identity), db: Session = Depends(session)):
    return {'contract_version':1,'markets':[market_view(row) for row in db.scalars(select(Market).order_by(Market.id))]}


@router.get('/markets/{market_id}/items')
def items(market_id: MarketId, q: str = Query('',max_length=32), after_id: int = Query(0,ge=0,le=2**31-1),
          limit: int = Query(50,ge=1,le=100), user: User = Depends(identity), db: Session = Depends(session)):
    market = require_market(db,market_id)
    latest = latest_observation(db,market_id)
    if not latest:
        return {'items':[],'market':market_view(market),'next_after_id':None,'synthetic':False}
    query = select(Listing.item_id,Listing.variant_key,Listing.variant).where(
        Listing.snapshot_id == latest.snapshot_id,Listing.item_id > after_id)
    if q:
        if not q.isdigit():
            # Item metadata lookup is deliberately explicit until upstream names are verified.
            return {'items':[],'market':market_view(market),'next_after_id':None,'synthetic':latest.synthetic,
                    'search_notice':'Item names are not indexed yet; search by numeric item ID.'}
        if int(q) > 2**31-1:
            return {'items':[],'market':market_view(market),'next_after_id':None,'synthetic':latest.synthetic}
        query = query.where(Listing.item_id == int(q))
    # Paginate item IDs, keeping every variant of the last item together.
    ids = list(db.scalars(query.with_only_columns(Listing.item_id).distinct().order_by(Listing.item_id).limit(limit+1)))
    page_ids = ids[:limit]
    rows = db.execute(query.where(Listing.item_id.in_(page_ids)).distinct().order_by(Listing.item_id,Listing.variant_key)) if page_ids else []
    return {'items':[{'item_id':row.item_id,'name':f'Item #{row.item_id}','name_verified':False,
                      'variant_key':row.variant_key,'variant':json.loads(row.variant)} for row in rows],
            'market':market_view(market),'next_after_id':page_ids[-1] if len(ids)>limit else None,'synthetic':latest.synthetic}


@router.get('/markets/{market_id}/items/{item_id}/{variant_key}')
def item_detail(market_id: MarketId, item_id: Annotated[int,Path(ge=1,le=2**31-1)], variant_key: str,
                user: User = Depends(identity), db: Session = Depends(session)):
    market = require_market(db,market_id)
    if len(variant_key) != 64 or any(char not in '0123456789abcdef' for char in variant_key):
        raise HTTPException(422,'Invalid variant key')
    latest = latest_observation(db,market_id)
    listings = list(db.scalars(select(Listing).where(Listing.snapshot_id == latest.snapshot_id,
        Listing.item_id == item_id,Listing.variant_key == variant_key).order_by(Listing.auction_id).limit(201))) if latest else []
    result = values(db,market_id,item_id,variant_key)
    return money_contract({'contract_version':1,'market':market_view(market),'item_id':item_id,'variant_key':variant_key,
        'name':f'Item #{item_id}','name_verified':False,'valuation':result,
        'listings':[{'auction_id':str(row.auction_id),'quantity':row.quantity,'buyout':row.buyout,
                     'unit_price':row.unit_price,'bid':row.bid,'time_left':row.time_left} for row in listings[:200]],
        'listings_truncated':len(listings)>200,'provenance':'asking_listings_only'})


@router.get('/markets/{market_id}/deals')
def deals(market_id: MarketId, minimum_discount: int = Query(15,ge=1,le=99),
          maximum_spend: int = Query(5000000,ge=1,le=2**53-1), minimum_coverage: int = Query(3,ge=1,le=60),
          user: User = Depends(identity), db: Session = Depends(session)):
    market = require_market(db,market_id)
    latest = latest_observation(db,market_id)
    if not latest:
        return {'deals':[],'candidates_truncated':False,'synthetic':False,'market':market_view(market)}
    rows = list(db.scalars(select(Listing).where(Listing.snapshot_id == latest.snapshot_id,
        (Listing.buyout.is_not(None) | Listing.unit_price.is_not(None)))
        .order_by(Listing.item_id,Listing.variant_key,Listing.auction_id).limit(1001)))
    cache, result = {}, []
    truncated = len(rows)>1000
    for row in rows[:1000]:
        key = row.item_id,row.variant_key
        if key not in cache:
            if len(cache)>=50:
                truncated = True
                continue
            cache[key] = values(db,market_id,*key)
        valuation = cache[key]
        reference = valuation['market_value']
        if not reference or valuation['market_coverage_days'] < minimum_coverage:
            continue
        total = row.buyout if row.buyout is not None else row.unit_price*row.quantity
        price = Decimal(total)/row.quantity
        discount = (1-price/Decimal(reference))*100
        if total > maximum_spend or discount < minimum_discount:
            continue
        result.append({'auction_id':str(row.auction_id),'item_id':row.item_id,'variant_key':row.variant_key,
            'quantity':row.quantity,'total_buyout':total,'market_value':reference,
            'discount_percent':round(float(discount),2),'coverage_days':valuation['market_coverage_days'],
            'confidence':'limited' if market_view(market)['freshness']!='current' else 'moderate',
            'reason':f'{discount:.1f}% below provisional 14-day asking-price reference; {valuation["market_coverage_days"]} observed days.',
            'cautions':['Asking prices do not establish completed sales or resale profit.',
                        'Workshop algorithm compatibility is not verified.']})
    result.sort(key=lambda row:(-row['discount_percent'],int(row['auction_id'])))
    return money_contract({'contract_version':1,'deals':result[:100],'candidates_truncated':truncated or len(result)>100,
        'synthetic':latest.synthetic or any(value['synthetic'] for value in cache.values()),
        'market':market_view(market),'algorithm':'asking-v1-provisional'})


@router.get('/markets/{market_id}/items/{item_id}/{variant_key}/history')
def historical_series(market_id: MarketId,item_id: Annotated[int,Path(ge=1,le=2**31-1)],variant_key: str,
                      days: int = Query(365,ge=1,le=3650),user: User = Depends(identity),db: Session = Depends(session)):
    require_market(db,market_id)
    if len(variant_key)!=64 or any(char not in '0123456789abcdef' for char in variant_key):
        raise HTTPException(422,'Invalid variant key')
    return money_contract({'contract_version':1,'market_id':market_id,'item_id':item_id,'variant_key':variant_key,
                           **daily_history(db,market_id,item_id,variant_key,days)})


class MarketCreate(BaseModel):
    region: Literal['us','eu','kr','tw']
    ruleset_id: int = Field(gt=0,le=2**31-1)
    house_id: int = Field(gt=0,le=2**31-1)
    source_kind: Literal['auctions','commodities']
    label: str = Field(min_length=1,max_length=100)
    interval_seconds: int = Field(default=1800,ge=300,le=86400)


class ScheduleUpdate(BaseModel):
    enabled: bool
    interval_seconds: int = Field(ge=300,le=86400)


@router.post('/admin/markets',status_code=201)
def create_market(body: MarketCreate,user: User = Depends(admin),db: Session = Depends(session)):
    row = Market(**body.model_dump(),enabled=False,verified=False)
    db.add(row)
    audit(db,user.id,'market.created')
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Market mapping already exists')
    return market_view(row)


@router.patch('/admin/markets/{market_id}/schedule')
def update_schedule(market_id: MarketId,body: ScheduleUpdate,user: User = Depends(admin),db: Session = Depends(session)):
    row = db.scalar(select(Market).where(Market.id==market_id).with_for_update())
    if not row:
        raise HTTPException(404,'Market not found')
    if body.enabled and not row.verified:
        raise HTTPException(409,'Live mapping verification required before enabling collection')
    row.enabled,row.interval_seconds = body.enabled,body.interval_seconds
    row.next_check = now()
    audit(db,user.id,'market.schedule_updated',str(row.id))
    db.commit()
    return market_view(row)


@router.get('/admin/collection-runs')
def collection_runs(after_id: int = Query(0,ge=0),limit: int = Query(100,ge=1,le=200),
                    user: User = Depends(admin),db: Session = Depends(session)):
    rows = list(db.scalars(select(CollectionRun).where(CollectionRun.id>after_id).order_by(CollectionRun.id).limit(limit+1)))
    return {'runs':[{'id':row.id,'market_id':row.market_id,'checked_at':row.checked_at,'status':row.status,
        'http_status':row.http_status,'duration_seconds':row.duration_seconds,'payload_bytes':row.payload_bytes,
        'error':row.error} for row in rows[:limit]],'next_after_id':rows[limit-1].id if len(rows)>limit else None}


@router.get('/admin/storage')
def storage(user: User = Depends(admin),db: Session = Depends(session)):
    size = db.scalar(text('SELECT pg_database_size(current_database())')) if db.bind.dialect.name=='postgresql' else None
    return {'database_bytes':size,'snapshots':db.scalar(select(func.count()).select_from(Snapshot)),
            'observations':db.scalar(select(func.count()).select_from(Observation)),
            'retention':{'historical_observations':'indefinite_private','guidance':'owner_provided_original_pending',
                         'raw_listing_days':int(os.environ.get('RAW_LISTING_DAYS','2')),
                         'detailed_statistics_days':int(os.environ.get('DETAILED_STATISTICS_DAYS','64')),
                         'daily_statistics':'indefinite_private',
                         'compaction_enabled':os.environ.get('HISTORY_COMPACTION_ENABLED','false').lower()=='true'},
            'backup':backup_state()}
