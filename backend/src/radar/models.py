from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Computed,
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
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
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
    date_basis: Mapped[str] = mapped_column(String(32), default="unknown")
    date_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence.id", use_alter=True, name="fk_events_date_evidence")
    )
    merged_into_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("events.id", name="fk_events_merged_into")
    )
    date_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="published")
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    content_version: Mapped[int] = mapped_column(Integer, default=1)
    search_document: Mapped[str] = mapped_column(Text, default="")
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector( 'simple', coalesce(search_document, ''))", persisted=True),
    )
    search_config_version: Mapped[str] = mapped_column(String(32), default="cjk-bigram-v1")
    search_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class EmbeddingProfileRow(Base):
    __tablename__ = "embedding_profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    provider: Mapped[str] = mapped_column(String(100))
    model_id: Mapped[str] = mapped_column(String(200))
    revision: Mapped[str] = mapped_column(String(200))
    dimension: Mapped[int] = mapped_column(Integer)
    normalize: Mapped[bool] = mapped_column(Boolean)
    input_template_version: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RetrievalSnapshotRow(Base):
    __tablename__ = "retrieval_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    filters_hash: Mapped[str] = mapped_column(String(64))
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    data_revision: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
    title: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="legacy")
    category: Mapped[str | None] = mapped_column(String(32))
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class ArticleSummaryTranslationRow(Base):
    __tablename__ = "article_summary_translations"
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    summary_hash: Mapped[str] = mapped_column(String(64))
    translated_text: Mapped[str | None] = mapped_column(Text)
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


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
    claim_key: Mapped[str | None] = mapped_column(String(100))
    claim_text: Mapped[str | None] = mapped_column(Text)
    quote_hash: Mapped[str | None] = mapped_column(String(64))
    support_type: Mapped[str] = mapped_column(String(24), default="direct")
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified")
    article_version: Mapped[ArticleVersionRow] = relationship()
    event: Mapped[EventRow] = relationship(foreign_keys=[event_id])


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


class EventMergeLogRow(Base):
    __tablename__ = "event_merge_log"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    source_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), index=True)
    target_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)
    operator: Mapped[str] = mapped_column(String(200))
    before_state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reverted_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventDateAuditLogRow(Base):
    __tablename__ = "event_date_audit_log"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id"))
    before_date: Mapped[date | None] = mapped_column(Date)
    before_precision: Mapped[str] = mapped_column(String(12))
    before_basis: Mapped[str] = mapped_column(String(32))
    after_date: Mapped[date] = mapped_column(Date)
    after_precision: Mapped[str] = mapped_column(String(12))
    after_basis: Mapped[str] = mapped_column(String(32))
    operator: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentTaskRow(Base):
    __tablename__ = "content_tasks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    article_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("article_versions.id"))
    content_hash: Mapped[str] = mapped_column(String(64))
    export_scope: Mapped[dict[str, str] | None] = mapped_column(JSONB)
    prompt_version: Mapped[str] = mapped_column(String(32), default="content-v1")
    schema_version: Mapped[str] = mapped_column(String(32), default="extraction-v1")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    mode: Mapped[str] = mapped_column(String(16), default="manual")
    draft_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("article_version_id", name="uq_content_task_version"),)


class ContentDraftRow(Base):
    __tablename__ = "content_drafts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_tasks.id"), unique=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    validation_errors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(24), default="needs_review")
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ContentSettingsRow(Base):
    __tablename__ = "content_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    batch_limit: Mapped[int] = mapped_column(Integer, default=5)
    daily_article_limit: Mapped[int] = mapped_column(Integer, default=0)
    daily_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    daily_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    article_max_calls: Mapped[int] = mapped_column(Integer, default=1)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=1600)
    concurrency: Mapped[int] = mapped_column(Integer, default=1)
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    profile_version: Mapped[int] = mapped_column(Integer, default=1)


class ContentBatchRow(Base):
    __tablename__ = "content_batches"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB)
    profile_version: Mapped[int] = mapped_column(Integer)
    auto_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentUsageRow(Base):
    __tablename__ = "content_usage"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_tasks.id"), unique=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_batches.id"))
    usage_day: Mapped[date] = mapped_column(Date)
    reserved_input_tokens: Mapped[int] = mapped_column(Integer)
    reserved_output_tokens: Mapped[int] = mapped_column(Integer)
    actual_input_tokens: Mapped[int | None] = mapped_column(Integer)
    actual_output_tokens: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="reserved")
    error_code: Mapped[str | None] = mapped_column(String(64))
