from datetime import timedelta
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from market.capacity import filesystem, status
from market.db import now
from market.models import Market, Observation
from market.worker import collect_once
from test_worker import Client, scheduled


def test_filesystem_guard_and_recovery(database, scheduled, monkeypatch):
    monkeypatch.setenv('MIN_DATABASE_FREE_BYTES', '1000')
    monkeypatch.setattr('market.capacity.os.statvfs', lambda _: SimpleNamespace(f_bavail=10, f_frsize=100, f_blocks=100))
    at = now()
    client = Client()
    collect_once(database, client, at=at)
    assert client.calls == 0
    with database() as db:
        assert 'free-space reserve' in db.get(Market, scheduled).last_error
    monkeypatch.setattr('market.capacity.os.statvfs', lambda _: SimpleNamespace(f_bavail=11, f_frsize=100, f_blocks=100))
    collect_once(database, client, at=at+timedelta(seconds=301))
    with database() as db:
        assert db.get(Market, scheduled).last_error is None
        assert db.scalar(select(Observation.id))


def test_unavailable_filesystem_fails_closed(database, monkeypatch):
    monkeypatch.delenv('DATABASE_FILESYSTEM_PATH')
    with database() as db:
        assert 'unavailable' in status(db)['paused_reason']
    assert filesystem()['available_bytes'] is None
    monkeypatch.setenv('MIN_DATABASE_FREE_BYTES', '0')
    with pytest.raises(ValueError): filesystem()


def test_cap_adjustment_resumes_collection(database, scheduled):
    with database() as db:
        if db.bind.dialect.name != 'postgresql': pytest.skip('PostgreSQL allocation')
    at = now()
    client = Client()
    collect_once(database, client, at=at, max_database_bytes=1)
    assert not client.calls
    collect_once(database, client, at=at+timedelta(seconds=301), max_database_bytes=1024**4)
    assert client.calls == 1
