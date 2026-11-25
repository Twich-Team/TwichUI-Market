import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select

from market.models import SecurityEvent, User, WaylaidReward
from market.waylaid_rewards import RewardConflict, reward_settings, save_reward


def test_new_tiers_start_unconfigured_and_null_edits_persist(database):
    with database() as db:
        actor = db.scalar(select(User))
        settings = reward_settings(db, {'expert', 'master'})
        assert [row['tier'] for row in settings] == ['apprentice', 'journeyman', 'expert', 'artisan', 'master']
        assert settings[-1]['favor'] is None and settings[-1]['revision'] == 0
        created = save_reward(db, actor, 'master', 25, 0)
        assert created['favor'] == 25 and created['revision'] == 1 and created['updated_by'] == 'owner'
    with database() as db:
        actor = db.scalar(select(User))
        cleared = save_reward(db, actor, 'master', None, 1)
        assert cleared['favor'] is None and cleared['revision'] == 2
    with database() as db:
        assert db.get(WaylaidReward, 'master').favor is None
        events = db.scalars(select(SecurityEvent).order_by(SecurityEvent.id)).all()
        assert [event.action for event in events] == ['waylaid_crates.reward_changed'] * 2
        assert 'previous=25 favor=None revision=2' in events[-1].detail


@pytest.mark.skipif(os.environ.get('DATABASE_URL') == 'sqlite://', reason='Requires PostgreSQL writer concurrency')
@pytest.mark.parametrize('revision', [0, 1])
def test_simultaneous_reward_insert_and_edit_have_one_winner(database, revision):
    if revision:
        with database.begin() as db:
            db.add(WaylaidReward(tier='expert', favor=15, revision=1))
    ready = Barrier(2)

    def edit(favor):
        with database() as db:
            actor = db.scalar(select(User))
            ready.wait(timeout=5)
            try:
                return save_reward(db, actor, 'expert', favor, revision)['favor']
            except RewardConflict:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, [20, 30]))
    assert results.count(None) == 1
    with database() as db:
        row = db.get(WaylaidReward, 'expert')
        assert row.favor in results and row.favor is not None and row.revision == revision + 1
        assert db.scalar(select(func.count()).select_from(SecurityEvent)) == 1
