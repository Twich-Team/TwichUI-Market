"""Administrator-maintained Merchant's Favor settings."""
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .db import now
from .models import User, WaylaidReward
from .security import audit

DEFAULT_REWARDS = {'apprentice': 5, 'journeyman': 10, 'expert': 15, 'artisan': None}


class RewardConflict(Exception):
    """A reward changed after the administrator loaded it."""


def rewards_by_tier(db: Session):
    return {reward.tier: reward for reward in db.scalars(select(WaylaidReward))}


def reward_view(tier, reward, username=None):
    return {
        'tier': tier,
        'favor': reward.favor if reward else None,
        'revision': reward.revision if reward else 0,
        'updated_at': reward.updated_at if reward else None,
        'updated_by': username,
    }


def reward_settings(db: Session, tiers: set[str]):
    records = db.execute(select(WaylaidReward, User.username).outerjoin(User, WaylaidReward.updated_by == User.id))
    by_tier = {record.tier: (record, username) for record, username in records}
    order = list(DEFAULT_REWARDS)
    order.extend(sorted((tiers | by_tier.keys()) - DEFAULT_REWARDS.keys()))
    return [reward_view(tier, *by_tier.get(tier, (None, None))) for tier in order]


def save_reward(db: Session, user: User, tier: str, favor: int | None, revision: int):
    existing = db.get(WaylaidReward, tier)
    previous = existing.favor if existing else None
    values = {'favor': favor, 'revision': revision + 1, 'updated_at': now(), 'updated_by': user.id}
    if revision == 0:
        insert = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
        statement = insert(WaylaidReward).values(tier=tier, **values).on_conflict_do_nothing()
    else:
        statement = update(WaylaidReward).where(
            WaylaidReward.tier == tier, WaylaidReward.revision == revision,
        ).values(**values)
    result = db.execute(statement.returning(WaylaidReward), execution_options={'populate_existing': True})
    saved = result.scalar_one_or_none()
    if saved is None:
        raise RewardConflict(tier)
    audit(db, user.id, 'waylaid_crates.reward_changed',
          f'tier={tier} previous={previous} favor={favor} revision={saved.revision}')
    db.commit()
    return reward_view(tier, saved, user.username)
