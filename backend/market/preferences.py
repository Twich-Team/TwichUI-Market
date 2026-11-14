"""Self-service website preferences. No user ID input and no collection mutations."""
import json
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import now, session
from .models import Market, User, UserPreference
from .security import audit, identity

router = APIRouter(prefix='/api/v1/me/preferences')
Column = Literal['recent_price','market_value','supply','listing_count','item_id']
SortColumn = Literal['name','recent_price','market_value','supply','listing_count','item_id']
Days = Literal[7,14,60,365,3650]
PageSize = Literal[25,50,100]
Mode = Literal['listings','supply','price']
Confidence = Literal['limited','moderate','strong']
Direction = Literal['any','increase','decrease']
MarketID = Annotated[int, Field(strict=True, ge=1, le=2**31-1)]
Change = Annotated[int, Field(strict=True, ge=1, le=1000)]
Coverage = Annotated[int, Field(strict=True, ge=1, le=15)]
Spend = Annotated[float, Field(strict=True, ge=0.01, le=100000000, allow_inf_nan=False)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class ItemSort(StrictModel):
    id: SortColumn = 'item_id'
    desc: StrictBool = False


class Preferences(StrictModel):
    market_id: MarketID | None = None
    explorer_days: Days = 14
    item_page_size: PageSize = 25
    item_columns: dict[Column, StrictBool] = Field(default_factory=lambda:{
        'recent_price':True,'market_value':True,'supply':True,'listing_count':True,'item_id':True}, max_length=5)
    item_sort: ItemSort = Field(default_factory=ItemSort)
    deal_mode: Mode = 'listings'
    deal_change: Change = 15
    deal_spend_gold: Spend = 500.0
    deal_coverage: Coverage = 3
    deal_confidence: Confidence = 'limited'
    deal_direction: Direction = 'any'


class Changes(StrictModel):
    market_id: MarketID | None = None
    explorer_days: Days | None = None
    item_page_size: PageSize | None = None
    item_columns: dict[Column, StrictBool] | None = Field(default=None, max_length=5)
    item_sort: ItemSort | None = None
    deal_mode: Mode | None = None
    deal_change: Change | None = None
    deal_spend_gold: Spend | None = None
    deal_coverage: Coverage | None = None
    deal_confidence: Confidence | None = None
    deal_direction: Direction | None = None


class Revision(StrictModel):
    schema_version: Annotated[int, Field(strict=True, ge=1, le=1)]
    expected_revision: Annotated[int, Field(strict=True, ge=0, le=2**53-2)]


class Update(Revision):
    changes: Changes


def browser_member(request: Request, user: User = Depends(identity)):
    if request.state.credential.kind != 'session':
        raise HTTPException(403, 'Website session required for personal preferences')
    return user


def read_values(row):
    if row is None:
        return Preferences().model_dump()
    if row.schema_version != 1:
        raise HTTPException(409, 'This preferences version requires a newer website')
    # Defaults fill fields added compatibly within this schema version.
    return Preferences.model_validate(json.loads(row.values_json)).model_dump()


def resource(db, row):
    values = read_values(row)
    # Disabled historical markets remain legitimate personal research choices.
    ids = list(db.scalars(select(Market.id).order_by(Market.enabled.desc(), Market.id)))
    chosen = values['market_id']
    effective = chosen if chosen in ids else next(iter(ids), None)
    return {'schema_version':1, 'revision':row.revision if row else 0, 'values':values,
        'effective_market_id':effective, 'market_fallback':chosen is not None and chosen not in ids,
        'updated_at':row.updated_at if row else None}


@router.get('')
def get_preferences(user: User = Depends(browser_member), db: Session = Depends(session)):
    return resource(db, db.get(UserPreference, user.id))


def write_preferences(db, user, body, *, reset=False):
    # User row exists even before first preference write: serializes concurrent first inserts.
    db.scalar(select(User.id).where(User.id==user.id).with_for_update())
    row = db.get(UserPreference, user.id, populate_existing=True)
    current_revision = row.revision if row else 0
    if body.expected_revision != current_revision:
        raise HTTPException(409, 'Preferences changed elsewhere; reload and merge your latest choices')
    values = read_values(row)
    if reset:
        values = Preferences().model_dump()
    else:
        changes = body.changes.model_dump(exclude_unset=True)
        if any(value is None and key!='market_id' for key,value in changes.items()):
            raise HTTPException(422, 'Only the preferred market can be null')
        if changes.get('market_id') is not None and db.get(Market, changes['market_id']) is None:
            raise HTTPException(422, 'Choose an available market')
        if 'item_columns' in changes:
            changes['item_columns'] = {**values['item_columns'], **changes['item_columns']}
        values = Preferences.model_validate({**values, **changes}).model_dump()
    encoded = json.dumps(values, separators=(',',':'), allow_nan=False)
    if len(encoded.encode()) > 4096:
        raise HTTPException(413, 'Preferences exceed the stored size limit')
    if row is None:
        row = UserPreference(user_id=user.id, schema_version=1, revision=0, values_json=encoded)
        db.add(row)
    row.values_json = encoded
    row.revision = current_revision+1
    row.updated_at = now()
    if reset:
        audit(db, user.id, 'preferences.reset', f'revision={row.revision}')
    db.commit()
    return resource(db, row)


@router.patch('')
def update_preferences(body: Update, user: User = Depends(browser_member), db: Session = Depends(session)):
    return write_preferences(db, user, body)


@router.post('/reset')
def reset_preferences(body: Revision, user: User = Depends(browser_member), db: Session = Depends(session)):
    return write_preferences(db, user, body, reset=True)
