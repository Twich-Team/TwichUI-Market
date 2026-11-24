"""Synthetic private-download browser fixture; only the running market_test API."""
import os
from pathlib import Path
import sys
import pytest
from market.db import Session,engine
from market.models import User
from market.security import hasher

assert engine.url.database=='market_test','Refusing private-beta fixtures in a non-test database'
sys.path.insert(0,'/app/tests')
from test_companion_private_beta import fixture_beta
with Session.begin() as db:
    assert db.get(User,10001) is None,'Synthetic pilot must start absent'
    db.add(User(id=10001,username='private_pilot',password_hash=hasher.hash('synthetic private pilot password'),role='member'))
with pytest.MonkeyPatch.context() as patch:
    root,_,_,_=fixture_beta(Path('/tmp/companion-private-beta-fixtures'),patch)
    assert str(root)==os.environ['COMPANION_PRIVATE_BETA_DIRECTORY']
print('Synthetic private beta and private_pilot seeded only in running market_test API temporary storage.')
