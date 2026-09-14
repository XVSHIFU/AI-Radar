"""Record idempotent offline event extraction calls and provider usage."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_llm_extraction"
down_revision: str | None = "0005_source_cooldown"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "llm_calls",
        sa.Column(
            "article_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("article_versions.id"),
        ),
    )
    op.add_column("llm_calls", sa.Column("provider_response_id", sa.String(200)))
    op.add_column("llm_calls", sa.Column("prompt_tokens", sa.Integer()))
    op.add_column("llm_calls", sa.Column("completion_tokens", sa.Integer()))
    op.add_column("llm_calls", sa.Column("total_tokens", sa.Integer()))
    op.add_column("llm_calls", sa.Column("response_content_hash", sa.String(64)))
    op.add_column("llm_calls", sa.Column("error_code", sa.String(64)))
    op.add_column("llm_calls", sa.Column("finished_at", sa.DateTime(timezone=True)))
    op.create_index(
        "uq_llm_event_extraction_version",
        "llm_calls",
        ["article_version_id"],
        unique=True,
        postgresql_where=sa.text("purpose = 'event_extraction'"),
    )


def downgrade() -> None:
    op.drop_index("uq_llm_event_extraction_version", table_name="llm_calls")
    op.drop_column("llm_calls", "finished_at")
    op.drop_column("llm_calls", "error_code")
    op.drop_column("llm_calls", "response_content_hash")
    op.drop_column("llm_calls", "total_tokens")
    op.drop_column("llm_calls", "completion_tokens")
    op.drop_column("llm_calls", "prompt_tokens")
    op.drop_column("llm_calls", "provider_response_id")
    op.drop_column("llm_calls", "article_version_id")
