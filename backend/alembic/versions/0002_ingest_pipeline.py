"""Persistent ingest queue, immutable article metadata and budget ledger."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_ingest_pipeline"
down_revision: str | None = "0001_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("etag", sa.String(500)))
    op.add_column("sources", sa.Column("last_modified", sa.String(500)))
    op.add_column("sources", sa.Column("last_checked_at", sa.DateTime(timezone=True)))
    op.add_column(
        "sources", sa.Column("canonical_host", sa.String(255), nullable=False, server_default="")
    )
    op.add_column(
        "sources", sa.Column("channel_type", sa.String(24), nullable=False, server_default="rss")
    )
    op.create_index(
        "uq_article_version_content",
        "article_versions",
        ["article_id", "content_hash"],
        unique=True,
    )
    op.create_table(
        "ingest_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("trigger_type", sa.String(24), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("discovered_urls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched_articles", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_articles", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_articles", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("event_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parser_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(18, 6)),
        sa.Column("cost_status", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("error_summary", sa.Text()),
    )
    op.create_table(
        "ingest_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingest_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False
        ),
        sa.Column("stage", sa.String(32), nullable=False, server_default="rss_fetch"),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column(
            "not_before", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("lease_owner", sa.String(200)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
    )
    op.create_index("ix_ingest_jobs_claim", "ingest_jobs", ["state", "not_before", "lease_until"])
    op.create_table(
        "article_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingest_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False
        ),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="needs_review"),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("source_id", "canonical_url", name="uq_candidate_source_url"),
    )
    op.create_table(
        "llm_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ingest_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingest_runs.id")),
        sa.Column("logical_request_id", sa.String(200), nullable=False),
        sa.Column("purpose", sa.String(48), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("reserved_cost", sa.Numeric(18, 6)),
        sa.Column("estimated_cost", sa.Numeric(18, 6)),
        sa.Column("actual_cost", sa.Numeric(18, 6)),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("cost_status", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(24), nullable=False),
    )
    op.create_table(
        "budget_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("logical_request_id", sa.String(200), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("state", sa.String(16), nullable=False, server_default="reserved"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("settled_cost", sa.Numeric(18, 6)),
    )
    op.create_index("ix_budget_reservations_scope", "budget_reservations", ["scope"])


def downgrade() -> None:
    op.drop_table("budget_reservations")
    op.drop_table("llm_calls")
    op.drop_table("article_candidates")
    op.drop_table("ingest_jobs")
    op.drop_table("ingest_runs")
    op.drop_index("uq_article_version_content", table_name="article_versions")
    op.drop_column("sources", "channel_type")
    op.drop_column("sources", "canonical_host")
    op.drop_column("sources", "last_checked_at")
    op.drop_column("sources", "last_modified")
    op.drop_column("sources", "etag")
