from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SourceRow(Base):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    feed_url: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health: Mapped[str] = mapped_column(String(32), default="unknown")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    etag: Mapped[str | None] = mapped_column(String(500))
    last_modified: Mapped[str | None] = mapped_column(String(500))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canonical_host: Mapped[str] = mapped_column(String(255), default="")
    channel_type: Mapped[str] = mapped_column(String(24), default="rss")
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EventRow(Base):
    __tablename__ = "events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    title_zh: Mapped[str] = mapped_column(Text)
    summary_zh: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), index=True)
    importance: Mapped[int] = mapped_column(Integer)
    event_date: Mapped[date | None] = mapped_column(Date)
    date_precision: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(16), default="published")
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    content_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    entities: Mapped[list[EventEntityRow]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    __table_args__ = (
        Index(
            "ix_events_date_id",
            event_date.desc(),
            id.desc(),
            postgresql_where=(status == "published"),
        ),
    )


class EntityRow(Base):
    __tablename__ = "entities"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(200), unique=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    aliases: Mapped[list[EntityAliasRow]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class EntityAliasRow(Base):
    __tablename__ = "entity_aliases"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    normalized_alias: Mapped[str] = mapped_column(String(200), index=True)
    alias_source: Mapped[str] = mapped_column(String(32), default="curated")
    entity: Mapped[EntityRow] = relationship(back_populates="aliases")


class EventEntityRow(Base):
    __tablename__ = "event_entities"
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(24), default="subject")
    event: Mapped[EventRow] = relationship(back_populates="entities")
    entity: Mapped[EntityRow] = relationship()


class ArticleRow(Base):
    __tablename__ = "articles"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    canonical_url: Mapped[str] = mapped_column(Text, unique=True)


class EventArticleRow(Base):
    __tablename__ = "event_articles"
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    relation_type: Mapped[str] = mapped_column(String(24), default="supports")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class ArticleVersionRow(Base):
    __tablename__ = "article_versions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paragraphs: Mapped[dict[str, str]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceRow(Base):
    __tablename__ = "evidence"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    article_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("article_versions.id"))
    paragraph_id: Mapped[str] = mapped_column(String(100))
    quote_text: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified")
    article_version: Mapped[ArticleVersionRow] = relationship()
    event: Mapped[EventRow] = relationship()


class IngestRunRow(Base):
    __tablename__ = "ingest_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    trigger_type: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_urls: Mapped[int] = mapped_column(Integer, default=0)
    fetched_articles: Mapped[int] = mapped_column(Integer, default=0)
    new_articles: Mapped[int] = mapped_column(Integer, default=0)
    updated_articles: Mapped[int] = mapped_column(Integer, default=0)
    event_candidates: Mapped[int] = mapped_column(Integer, default=0)
    parser_failures: Mapped[int] = mapped_column(Integer, default=0)
    failed_jobs: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    cost_status: Mapped[str] = mapped_column(String(16), default="unknown")
    error_summary: Mapped[str | None] = mapped_column(Text)


class IngestJobRow(Base):
    __tablename__ = "ingest_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingest_runs.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    job_key: Mapped[str] = mapped_column(String(160), unique=True)
    stage: Mapped[str] = mapped_column(String(32), default="rss_fetch")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(24), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lease_owner: Mapped[str | None] = mapped_column(String(200))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_generation: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class ArticleCandidateRow(Base):
    __tablename__ = "article_candidates"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingest_runs.id", ondelete="CASCADE"))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    article_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("article_versions.id"))
    canonical_url: Mapped[str] = mapped_column(Text)
    original_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="needs_review")
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (
        UniqueConstraint("source_id", "article_version_id", name="uq_candidate_source_version"),
    )


class ArticleDiscoveryRow(Base):
    __tablename__ = "article_discoveries"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingest_runs.id", ondelete="CASCADE"))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    canonical_url: Mapped[str] = mapped_column(Text)
    original_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    published: Mapped[str | None] = mapped_column(Text)
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL")
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (
        UniqueConstraint(
            "run_id", "source_id", "canonical_url", name="uq_discovery_run_source_url"
        ),
    )


class LlmCallRow(Base):
    __tablename__ = "llm_calls"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    ingest_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingest_runs.id"))
    article_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("article_versions.id"))
    logical_request_id: Mapped[str] = mapped_column(String(200))
    request_payload_hash: Mapped[str | None] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(48))
    provider: Mapped[str] = mapped_column(String(100))
    model_id: Mapped[str] = mapped_column(String(200))
    attempt: Mapped[int] = mapped_column(Integer)
    reserved_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    actual_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    cost_status: Mapped[str] = mapped_column(String(16), default="unknown")
    status: Mapped[str] = mapped_column(String(24))
    provider_response_id: Mapped[str | None] = mapped_column(String(200))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    response_content_hash: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BudgetReservationRow(Base):
    __tablename__ = "budget_reservations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    scope: Mapped[str] = mapped_column(String(100), index=True)
    logical_request_id: Mapped[str] = mapped_column(String(200), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    state: Mapped[str] = mapped_column(String(16), default="reserved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    settled_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
