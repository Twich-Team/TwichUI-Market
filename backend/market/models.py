from datetime import date, datetime
from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base, now


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16), default="member")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Credential(Base):
    __tablename__ = "credentials"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(80), default="browser")
    csrf_hash: Mapped[str | None] = mapped_column(String(64))
    audience: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Market(Base):
    __tablename__ = "markets"
    __table_args__ = (UniqueConstraint("region", "ruleset_id", "house_id", "source_kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(String(2))
    ruleset_id: Mapped[int] = mapped_column(Integer)
    house_id: Mapped[int] = mapped_column(Integer)
    source_kind: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    next_check: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_modified: Mapped[str | None] = mapped_column(String(100))
    etag: Mapped[str | None] = mapped_column(String(200))
    failures: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(200))


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (UniqueConstraint("market_id", "content_hash"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    listing_count: Mapped[int] = mapped_column(Integer)
    raw_retained: Mapped[bool] = mapped_column(Boolean, default=True)
    statistics_retained: Mapped[bool] = mapped_column(Boolean, default=True)


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), index=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"), index=True)
    request_key: Mapped[str] = mapped_column(String(64), unique=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    upstream_modified: Mapped[str | None] = mapped_column(String(100))
    namespace: Mapped[str] = mapped_column(String(80))
    payload_hash: Mapped[str] = mapped_column(String(64))
    payload_bytes: Mapped[int] = mapped_column(Integer)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("snapshot_id", "auction_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"), index=True)
    auction_id: Mapped[int] = mapped_column(BigInteger)
    item_id: Mapped[int] = mapped_column(Integer, index=True)
    variant: Mapped[str] = mapped_column(Text)
    variant_key: Mapped[str] = mapped_column(String(64), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    buyout: Mapped[int | None] = mapped_column(BigInteger)
    unit_price: Mapped[int | None] = mapped_column(BigInteger)
    bid: Mapped[int | None] = mapped_column(BigInteger)
    time_left: Mapped[str | None] = mapped_column(String(32))


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    status: Mapped[str] = mapped_column(String(24))
    http_status: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    payload_bytes: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(200))


class SnapshotStatistic(Base):
    __tablename__ = 'snapshot_statistics'
    __table_args__=(Index('ix_snapshot_statistics_item_variant','item_id','variant_key'),)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey('snapshots.id'),primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer,primary_key=True)
    variant_key: Mapped[str] = mapped_column(String(64),primary_key=True)
    algorithm: Mapped[str] = mapped_column(String(80),default='asking-v1-provisional')
    recent_price: Mapped[int | None] = mapped_column(BigInteger)
    lowest_buyout: Mapped[int | None] = mapped_column(BigInteger)
    supply: Mapped[int] = mapped_column(BigInteger)
    priced_supply: Mapped[int] = mapped_column(BigInteger)
    listing_count: Mapped[int] = mapped_column(Integer)


class DailyObservation(Base):
    __tablename__ = 'daily_observations'
    market_id: Mapped[int] = mapped_column(ForeignKey('markets.id'),primary_key=True)
    day: Mapped[date] = mapped_column(Date,primary_key=True)
    observation_id: Mapped[int] = mapped_column(ForeignKey('observations.id'),index=True)


class ItemMetadata(Base):
    __tablename__='item_metadata'
    region: Mapped[str] = mapped_column(String(2),primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer,primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16),default='unresolved')
    namespace: Mapped[str] = mapped_column(String(80))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_after: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)
    http_status: Mapped[int | None] = mapped_column(Integer)
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    synthetic: Mapped[bool] = mapped_column(Boolean,default=False)
    quality: Mapped[str | None] = mapped_column(String(32))
    details: Mapped[str | None] = mapped_column(Text)
    resolved_namespace: Mapped[str | None] = mapped_column(String(100))
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fallback: Mapped[str | None] = mapped_column(Text)
    fallback_name: Mapped[str | None] = mapped_column(String(255))
    fallback_retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__=(Index('ix_item_metadata_region_name',region,func.lower(name)),)


class StorageMeasurement(Base):
    __tablename__='storage_measurements'
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),primary_key=True)
    database_bytes: Mapped[int] = mapped_column(BigInteger)


class MarketVerification(Base):
    __tablename__='market_verifications'
    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey('markets.id'),index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)
    evidence: Mapped[str] = mapped_column(Text)
    evidence_hash: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str] = mapped_column(Text)


class ItemMedia(Base):
    __tablename__='item_media'
    region: Mapped[str] = mapped_column(String(2),primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer,primary_key=True)
    status: Mapped[str] = mapped_column(String(16),default='pending')
    source: Mapped[str] = mapped_column(String(32),default='blizzard')
    source_url: Mapped[str | None] = mapped_column(String(512))
    namespace: Mapped[str | None] = mapped_column(String(100))
    metadata_hash: Mapped[str | None] = mapped_column(String(64))
    asset_hash: Mapped[str | None] = mapped_column(String(64))
    content_type: Mapped[str | None] = mapped_column(String(32))
    data: Mapped[bytes | None] = mapped_column(LargeBinary)
    byte_count: Mapped[int] = mapped_column(Integer,default=0)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RetentionPolicy(Base):
    __tablename__ = 'retention_policy'
    id: Mapped[int] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    raw_days: Mapped[int] = mapped_column(Integer, default=7)
    intraday_days: Mapped[int] = mapped_column(Integer, default=90)
    daily_days: Mapped[int] = mapped_column(Integer, default=365)
    operational_days: Mapped[int] = mapped_column(Integer, default=90)
    security_days: Mapped[int] = mapped_column(Integer, default=365)
    approved_hash: Mapped[str | None] = mapped_column(String(64))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RetentionBatch(Base):
    __tablename__ = 'retention_batches'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    policy_hash: Mapped[str] = mapped_column(String(64))
    stage: Mapped[str] = mapped_column(String(32))
    rows_removed: Mapped[int] = mapped_column(Integer)
    cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    history_floor: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class RetentionPolicyChange(Base):
    __tablename__ = 'retention_policy_changes'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    before: Mapped[str] = mapped_column(Text)
    after: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PlayerMarketMapping(Base):
    __tablename__ = 'player_market_mappings'
    __table_args__ = (UniqueConstraint('region','ruleset','faction','source_kind'),UniqueConstraint('region','house_id','source_kind'))
    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(String(2))
    ruleset: Mapped[str] = mapped_column(String(32))
    faction: Mapped[str] = mapped_column(String(16))
    house_id: Mapped[int] = mapped_column(Integer)
    transport_ruleset_id: Mapped[int] = mapped_column(Integer)
    source_kind: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[str] = mapped_column(String(32))
    evidence: Mapped[str] = mapped_column(Text)
    evidence_hash: Mapped[str] = mapped_column(String(64))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
