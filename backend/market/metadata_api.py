"""Additive authenticated local catalog export; never contacts a provider."""
import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import session
from .market_api import MarketId, metadata_name, require_market
from .metadata_recovery import observed_query
from .models import ItemMetadata, User
from .security import identity
router = APIRouter(prefix='/api/v1/metadata')


@router.get('/markets/{market_id}')
def catalog(market_id: MarketId, after_id: int = Query(0, ge=0, le=2**31-1), limit: int = Query(100, ge=1, le=500),
            user: User = Depends(identity), db: Session = Depends(session)):
    market = require_market(db, market_id)
    ids = observed_query(market_id).subquery()
    rows = list(db.execute(select(ids.c.item_id, ItemMetadata).outerjoin(ItemMetadata,
        (ItemMetadata.region == ids.c.region) & (ItemMetadata.item_id == ids.c.item_id)).where(ids.c.item_id > after_id).order_by(ids.c.item_id).limit(limit + 1)))
    return {'contract_version':1, 'edition':'forever', 'locale':'en_US', 'region':market.region,
        'items':[{'item_id':ident, **metadata_name(row, ident), 'revision':row.catalog_revision if row else 0,
            'catalog':json.loads(row.catalog_json) if row and row.catalog_json else None} for ident, row in rows[:limit]],
        'next_after_id':rows[limit-1][0] if len(rows) > limit else None}
