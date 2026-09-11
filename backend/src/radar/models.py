from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
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
