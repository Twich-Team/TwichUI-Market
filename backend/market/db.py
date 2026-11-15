import os
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


engine = create_engine(os.environ.get("DATABASE_URL", "sqlite:///./market.db"), pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)


def session():
    with Session() as db:
        yield db
