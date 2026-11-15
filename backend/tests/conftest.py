import os
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["COOKIE_SECURE"] = "false"
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from market.app import app
from market.db import Base, session
from market.models import User
from market.security import hasher


@pytest.fixture
def database():
    url = os.environ["DATABASE_URL"]
    if url != "sqlite://" and not url.endswith('/market_test'):
        pytest.fail('Refusing destructive tests: database must be named market_test')
    kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}} if url == "sqlite://" else {}
    engine = create_engine(url, **kwargs)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add(User(username="owner", password_hash=hasher.hash("correct horse battery"), role="admin"))
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[session] = override
    yield factory
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(database):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def owner(client):
    result = client.post('/api/v1/auth/login', json={'username': 'owner', 'password': 'correct horse battery'})
    assert result.status_code == 200
    client.headers['x-csrf-token'] = result.json()['csrf_token']
    return client
