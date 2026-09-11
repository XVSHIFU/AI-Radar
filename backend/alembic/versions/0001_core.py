"""Core event, entity, version and evidence tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_core"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("feed_url", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("health", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title_zh", sa.Text(), nullable=False),
        sa.Column("summary_zh", sa.Text(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("event_date", sa.Date()),
        sa.Column("date_precision", sa.String(12), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="published"),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("importance BETWEEN 1 AND 5", name="ck_event_importance"),
    )
    op.create_index(
        "ix_events_date_id",
        "events",
        [sa.text("event_date DESC"), sa.text("id DESC")],
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index(
        "ix_events_category_date_id",
        "events",
        ["category", sa.text("event_date DESC"), sa.text("id DESC")],
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_name", sa.String(200), nullable=False, unique=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
    )
    op.create_table(
        "entity_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("normalized_alias", sa.String(200), nullable=False),
        sa.Column("alias_source", sa.String(32), nullable=False),
    )
    op.create_table(
        "event_entities",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(24), nullable=False),
    )
    op.create_index("ix_event_entities_lookup", "event_entities", ["entity_id", "event_id"])
    op.create_index(
        "ix_entity_aliases_normalized_alias",
        "entity_aliases",
        ["normalized_alias"],
    )
    op.create_table(
        "articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
        sa.Column("canonical_url", sa.Text(), nullable=False, unique=True),
    )
    op.create_table(
        "event_articles",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "article_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("relation_type", sa.String(24), nullable=False, server_default="supports"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "article_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "article_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("paragraphs", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "article_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("article_versions.id"),
            nullable=False,
        ),
        sa.Column("paragraph_id", sa.String(100), nullable=False),
        sa.Column("quote_text", sa.Text(), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False),
    )
    op.create_index("ix_evidence_event_id", "evidence", ["event_id"])


def downgrade() -> None:
    op.drop_table("evidence")
    op.drop_table("article_versions")
    op.drop_table("event_articles")
    op.drop_table("articles")
    op.drop_table("event_entities")
    op.drop_table("entity_aliases")
    op.drop_table("entities")
    op.drop_table("events")
    op.drop_table("sources")
