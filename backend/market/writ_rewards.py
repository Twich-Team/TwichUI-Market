"""Reputation settings and precedence for one Crafting Writ completion."""
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .db import now
from .models import CraftingWritReward, User
from .security import audit


class RewardConflict(Exception):
    """The saved reward no longer has the editor's revision."""


def reward_settings(db: Session):
    rows = db.execute(select(CraftingWritReward, User.username).join(User))
    return {(row.scope, row.key): reward_view(row.key, row, username) for row, username in rows}


def reward_view(key, row=None, username=None):
    return {
        'key': key,
        'reputation': row.reputation if row else None,
        'revision': row.revision if row else 0,
        'updated_at': row.updated_at if row else None,
        'updated_by': username,
    }


def save_reward(db: Session, user: User, scope: str, key: str, reputation: int | None, revision: int):
    existing = db.get(CraftingWritReward, (scope, key))
    if revision != (existing.revision if existing else 0):
        raise RewardConflict((scope, key))
    previous = existing.reputation if existing else None
    changes = dict(reputation=reputation, revision=revision + 1, updated_at=now(), updated_by=user.id)
    if revision == 0:
        insert = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
        statement = insert(CraftingWritReward).values(scope=scope, key=key, **changes).on_conflict_do_nothing()
    else:
        statement = update(CraftingWritReward).where(
            CraftingWritReward.scope == scope,
            CraftingWritReward.key == key,
            CraftingWritReward.revision == revision,
        ).values(**changes)
    result = db.execute(statement.returning(CraftingWritReward), execution_options={'populate_existing': True})
    saved = result.scalar_one_or_none()
    if saved is None:
        raise RewardConflict((scope, key))
    view = reward_view(key, saved, user.username)
    audit(db, user.id, 'crafting_writs.reward_changed',
          f'scope={scope} key={key} previous={previous} reputation={reputation} revision={saved.revision}')
    db.commit()
    return view


def effective_reward(writ, settings):
    override = settings.get(('writ', str(writ['item_id'])), {}).get('reputation')
    tier = settings.get(('tier', writ.get('tier')), {}).get('reputation')
    provider = writ.get('provider_reward')
    if override is not None:
        return override, 'writ_override'
    if tier is not None:
        return tier, 'tier_setting'
    if provider is not None:
        return provider, 'provider'
    return None, 'unknown'
