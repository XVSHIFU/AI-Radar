"""Persist each model call's reservation within a public research question."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012_research_model_calls"
down_revision: str | None = "0011_public_ask_quota"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_model_calls",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public_ask_requests.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("sequence", sa.Integer(), primary_key=True),
        sa.Column(
            "model_call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("llm_calls.id"),
            nullable=False,
        ),
        sa.Column("input_reserved", sa.Integer(), nullable=False),
        sa.Column("output_reserved", sa.Integer(), nullable=False),
        sa.UniqueConstraint("model_call_id", name="uq_research_model_call"),
        sa.CheckConstraint("sequence BETWEEN 1 AND 3", name="ck_research_sequence"),
        sa.CheckConstraint("input_reserved BETWEEN 1 AND 24000", name="ck_research_input"),
        sa.CheckConstraint("output_reserved BETWEEN 1 AND 2000", name="ck_research_output"),
    )


def downgrade() -> None:
    op.drop_table("research_model_calls")
