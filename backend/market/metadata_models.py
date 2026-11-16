"""Additive catalog, provider controls and durable recovery queue models."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base, now


class MetadataProvider(Base):
    __tablename__ = 'metadata_providers'
    provider: Mapped[str] = mapped_column(String(24), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    automatic: Mapped[bool] = mapped_column(Boolean, default=False)
    hourly_budget: Mapped[int] = mapped_column(Integer, default=20)
    daily_budget: Mapped[int] = mapped_column(Integer, default=100)
    hour_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    day_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hour_used: Mapped[int] = mapped_column(Integer, default=0)
    day_used: Mapped[int] = mapped_column(Integer, default=0)
    next_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(40))
    credential: Mapped[bytes | None] = mapped_column(LargeBinary)
    credential_key_id: Mapped[str | None] = mapped_column(String(48))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credential_status: Mapped[str] = mapped_column(String(32), default='not_configured')
    pending_credential: Mapped[bytes | None] = mapped_column(LargeBinary)
    pending_key_id: Mapped[str | None] = mapped_column(String(48))
    pending_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_revision: Mapped[int] = mapped_column(Integer, default=0)
    validation_error: Mapped[str | None] = mapped_column(String(40))
    # Separate from credential envelopes; changing these never resets usage.
    rate_config: Mapped[str | None] = mapped_column(Text)
    rate_tokens: Mapped[float | None] = mapped_column(Float)
    rate_token_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rate_inflight_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rate_streak: Mapped[int] = mapped_column(Integer, default=0)
    adaptive_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_rate_limit: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_http_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_recovery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rate_observation: Mapped[str | None] = mapped_column(Text)


class MetadataQuotaBucket(Base):
    """At most 1,441 minute buckets/provider, plus minute-window second buckets."""
    __tablename__ = 'metadata_quota_buckets'
    provider: Mapped[str] = mapped_column(ForeignKey('metadata_providers.provider'), primary_key=True)
    resolution: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    used: Mapped[int] = mapped_column(Integer, default=0)


class MetadataSource(Base):
    __tablename__ = 'metadata_sources'
    region: Mapped[str] = mapped_column(String(2), primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    locale: Mapped[str] = mapped_column(String(8), primary_key=True, default='en_US')
    provider: Mapped[str] = mapped_column(String(24), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default='pending')
    fields_json: Mapped[str | None] = mapped_column(Text)
    source_json: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    etag: Mapped[str | None] = mapped_column(String(255))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (Index('ix_metadata_sources_due', 'provider', 'retry_at'),)


class MetadataVersion(Base):
    __tablename__ = 'metadata_versions'
    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(String(2))
    item_id: Mapped[int] = mapped_column(Integer)
    locale: Mapped[str] = mapped_column(String(8))
    provider: Mapped[str] = mapped_column(String(24))
    revision: Mapped[int] = mapped_column(Integer)
    fields_json: Mapped[str] = mapped_column(Text)
    source_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('region', 'item_id', 'locale', 'provider', 'revision', name='uq_metadata_version'),)


class MetadataJob(Base):
    __tablename__ = 'metadata_jobs'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    market_id: Mapped[int | None] = mapped_column(ForeignKey('markets.id'))
    mode: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), default='queued', index=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), index=True)
    providers_json: Mapped[str] = mapped_column(Text)
    total: Mapped[int] = mapped_column(Integer, default=0)
    request_budget: Mapped[int] = mapped_column(Integer, default=100)
    requests_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MetadataTask(Base):
    __tablename__ = 'metadata_tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('metadata_jobs.id'), index=True)
    provider: Mapped[str] = mapped_column(String(24))
    region: Mapped[str] = mapped_column(String(2))
    item_id: Mapped[int] = mapped_column(Integer)
    locale: Mapped[str] = mapped_column(String(8), default='en_US')
    state: Mapped[str] = mapped_column(String(16), default='queued')
    resource: Mapped[str | None] = mapped_column(String(80))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(48))
    result_json: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('job_id', 'provider', 'region', 'item_id', 'locale', name='uq_metadata_job_item'),
        Index('ix_metadata_tasks_queue', 'state', 'available_at'), Index('ix_metadata_tasks_identity', 'provider', 'region', 'item_id', 'locale', 'state'))


class MetadataResource(Base):
    """Bounded ForeverDB related-response cache in the existing metadata system."""
    __tablename__ = 'metadata_resources'
    region: Mapped[str] = mapped_column(String(2), primary_key=True)
    resource: Mapped[str] = mapped_column(String(80), primary_key=True)
    offset: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default='pending')
    fields_json: Mapped[str | None] = mapped_column(Text)
    source_json: Mapped[str | None] = mapped_column(Text)
    etag: Mapped[str | None] = mapped_column(String(255))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)
