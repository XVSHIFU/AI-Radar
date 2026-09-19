"""Persistent content tasks, drafts, batches and conservative usage reservations."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0014_content_workbench"
down_revision: str | None = "0013_public_quota_retention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "article_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("article_versions.id"),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("export_scope", JSONB),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True)),
        sa.Column("batch_id", UUID(as_uuid=True)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("article_version_id", name="uq_content_task_version"),
    )
    op.create_table(
        "content_drafts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("content_tasks.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("validation_errors", JSONB, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id")),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "content_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("auto_publish", sa.Boolean, nullable=False),
        sa.Column("batch_limit", sa.Integer, nullable=False),
        sa.Column("daily_article_limit", sa.Integer, nullable=False),
        sa.Column("daily_input_tokens", sa.Integer, nullable=False),
        sa.Column("daily_output_tokens", sa.Integer, nullable=False),
        sa.Column("article_max_calls", sa.Integer, nullable=False),
        sa.Column("max_output_tokens", sa.Integer, nullable=False),
        sa.Column("concurrency", sa.Integer, nullable=False),
        sa.Column("profile", JSONB, nullable=False),
        sa.Column("profile_version", sa.Integer, nullable=False),
        sa.CheckConstraint("id = 1", name="ck_content_settings_singleton"),
    )
    op.execute(
        "INSERT INTO content_settings "
        "(id, enabled, auto_publish, batch_limit, daily_article_limit, "
        "daily_input_tokens, daily_output_tokens, article_max_calls, "
        "max_output_tokens, concurrency, profile, profile_version) "
        "VALUES (1, false, false, 5, 0, 0, 0, 1, 1600, 1, '{}'::jsonb, 1)"
    )
    op.create_table(
        "content_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("profile", JSONB, nullable=False),
        sa.Column("profile_version", sa.Integer, nullable=False),
        sa.Column("auto_publish", sa.Boolean, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "content_usage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("content_tasks.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "batch_id", UUID(as_uuid=True), sa.ForeignKey("content_batches.id"), nullable=False
        ),
        sa.Column("usage_day", sa.Date, nullable=False),
        sa.Column("reserved_input_tokens", sa.Integer, nullable=False),
        sa.Column("reserved_output_tokens", sa.Integer, nullable=False),
        sa.Column("actual_input_tokens", sa.Integer),
        sa.Column("actual_output_tokens", sa.Integer),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(64)),
    )
    op.create_index("ix_content_usage_day", "content_usage", ["usage_day"])


def downgrade() -> None:
    op.drop_index("ix_content_usage_day", table_name="content_usage")
    for name in (
        "content_usage",
        "content_batches",
        "content_settings",
        "content_drafts",
        "content_tasks",
    ):
        op.drop_table(name)
