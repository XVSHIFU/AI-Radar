"""Persist anonymous public-question ownership, quota, and token reservations."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_public_ask_quota"
down_revision: str | None = "0010_admin_durable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_ask_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_hash", sa.String(64), nullable=False),
        sa.Column("client_request_id", sa.String(128), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("charged", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("input_charge", sa.Integer(), nullable=False),
        sa.Column("output_charge", sa.Integer(), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("owner_hash", "client_request_id", name="uq_public_ask_owner_request"),
    )
    op.create_index("ix_public_ask_ip_time", "public_ask_requests", ["ip_hash", "admitted_at"])
    op.create_index("ix_public_ask_admitted_at", "public_ask_requests", ["admitted_at"])


def downgrade() -> None:
    op.drop_table("public_ask_requests")
