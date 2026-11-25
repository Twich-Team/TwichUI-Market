from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from market.models import CollectionRun, Market, Snapshot, User
from market.security import hasher


def test_collection_activity_groups_the_entire_retained_window(owner, database, monkeypatch):
    from market import admin_records

    at = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(admin_records, "now", lambda: at)
    with database.begin() as db:
        market = Market(region="us", ruleset_id=2, house_id=113, source_kind="auctions", label="First market")
        other = Market(region="us", ruleset_id=2, house_id=114, source_kind="auctions", label="Other market")
        db.add_all([market, other])
        db.flush()
        market_id = market.id
        for offset in range(123):
            db.add(CollectionRun(market_id=market.id, status="unchanged",
                                 checked_at=at - timedelta(minutes=offset)))
        db.add_all([
            CollectionRun(market_id=market.id, status="collected", checked_at=at - timedelta(days=1)),
            CollectionRun(market_id=market.id, status="partial", error="Partial collection", checked_at=at - timedelta(days=1)),
            CollectionRun(market_id=market.id, status="failed", checked_at=at - timedelta(days=3)),
            CollectionRun(market_id=market.id, status="other_recorded", checked_at=at - timedelta(days=3)),
            # Recorded errors take precedence over a nominal success, except the distinct partial state.
            CollectionRun(market_id=market.id, status="collected", error="Failed validation", checked_at=at - timedelta(days=6, hours=12)),
            CollectionRun(market_id=market.id, status="unchanged", checked_at=at - timedelta(days=6, hours=12, seconds=1)),
            CollectionRun(market_id=market.id, status="collected", checked_at=at + timedelta(seconds=1)),
            CollectionRun(market_id=other.id, status="failed", checked_at=at),
            Snapshot(market_id=market.id, content_hash="a" * 64, listing_count=8, created_at=at - timedelta(days=1)),
            Snapshot(market_id=other.id, content_hash="b" * 64, listing_count=20, created_at=at),
        ])

    engine = database.kw["bind"]
    def set_timezone(connection):
        connection.exec_driver_sql("SET LOCAL TIME ZONE 'America/Los_Angeles'")
    if engine.dialect.name == "postgresql":
        event.listen(engine, "begin", set_timezone)
    try:
        scoped = owner.get("/api/v1/admin/records/collection-activity",
                           params={"market_id": market_id, "days": 7})
        overall = owner.get("/api/v1/admin/records/collection-activity", params={"days": 7})
    finally:
        if engine.dialect.name == "postgresql":
            event.remove(engine, "begin", set_timezone)

    assert scoped.status_code == overall.status_code == 200
    result = scoped.json()
    assert len(result["days"]) == 7
    first, *_, earlier, blank, yesterday, today = result["days"]
    assert first["date"] == "2026-11-18" and first["failed"] == first["checks"] == 1
    assert earlier["date"] == "2026-11-21" and earlier["failed"] == earlier["other"] == 1
    assert blank["date"] == "2026-11-22" and blank["checks"] == 0
    assert yesterday["collected"] == yesterday["partial"] == yesterday["snapshots"] == 1
    assert today["unchanged"] == today["checks"] == 123
    assert sum(day["checks"] for day in result["days"]) == 128
    assert datetime.fromisoformat(result["latest_snapshot_at"]).date().isoformat() == "2026-11-23"
    assert overall.json()["days"][-1]["failed"] == overall.json()["days"][-1]["snapshots"] == 1
    assert datetime.fromisoformat(overall.json()["latest_snapshot_at"]).date().isoformat() == "2026-11-24"


def test_collection_activity_is_admin_only_and_bounded(client, owner, database):
    assert owner.get("/api/v1/admin/records/collection-activity?days=91").status_code == 422
    empty = owner.get("/api/v1/admin/records/collection-activity?days=90").json()
    assert len(empty["days"]) == 90
    assert all(day["checks"] == 0 for day in empty["days"])
    assert empty["latest_snapshot_at"] is None
    with database.begin() as db:
        db.add(User(username="member", role="member", password_hash=hasher.hash("member fixture password")))
    assert client.post("/api/v1/auth/login", json={"username": "member", "password": "member fixture password"}).status_code == 200
    assert client.get("/api/v1/admin/records/collection-activity").status_code == 403


def test_collection_activity_preserves_snapshot_evidence_without_check_receipts(owner, database, monkeypatch):
    from market import admin_records

    at = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(admin_records, "now", lambda: at)
    with database.begin() as db:
        market = Market(region="us", ruleset_id=2, house_id=113, source_kind="auctions", label="Snapshots only")
        db.add(market)
        db.flush()
        market_id = market.id
        start = at - timedelta(days=6, hours=12)
        for index, created_at in enumerate([start - timedelta(seconds=1), start, at, at + timedelta(seconds=1)]):
            db.add(Snapshot(market_id=market_id, content_hash=str(index) * 64, listing_count=8, created_at=created_at))
    result = owner.get("/api/v1/admin/records/collection-activity",
                       params={"market_id": market_id, "days": 7}).json()
    assert [day["snapshots"] for day in result["days"]] == [1, 0, 0, 0, 0, 0, 1]
    assert all(day["checks"] == day["collected"] == day["failed"] == 0 for day in result["days"])
