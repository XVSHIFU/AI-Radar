"""Bind answer idempotency keys to payload hashes."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_answer_idempotency"
down_revision: str | None = "0006_llm_extraction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("llm_calls", sa.Column("request_payload_hash", sa.String(64)))
    op.create_index(
        "uq_llm_answer_logical_request",
        "llm_calls",
        ["logical_request_id"],
        unique=True,
        postgresql_where=sa.text("purpose = 'answer_generation'"),
    )


def downgrade() -> None:
    op.drop_index("uq_llm_answer_logical_request", table_name="llm_calls")
    op.drop_column("llm_calls", "request_payload_hash")
