"""Add traceable event dates, evidence claims and reversible event merges."""

from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0008_data_quality"
down_revision: str | None = "0007_answer_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("events", sa.Column("date_basis", sa.String(32), nullable=False, server_default="report_date_unverified"))
    op.add_column("events", sa.Column("date_evidence_id", postgresql.UUID(as_uuid=True)))
    op.add_column("events", sa.Column("merged_into_event_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key("fk_events_date_evidence", "events", "evidence", ["date_evidence_id"], ["id"])
    op.create_foreign_key("fk_events_merged_into", "events", "events", ["merged_into_event_id"], ["id"])
    op.create_check_constraint("ck_events_date_semantics", "events", "(date_precision = 'unknown' AND event_date IS NULL) OR (date_precision IN ('day', 'month') AND event_date IS NOT NULL)")
    op.add_column("evidence", sa.Column("claim_key", sa.String(100)))
    op.add_column("evidence", sa.Column("claim_text", sa.Text()))
    op.add_column("evidence", sa.Column("quote_hash", sa.String(64)))
    op.add_column("evidence", sa.Column("support_type", sa.String(24), nullable=False, server_default="direct"))
    op.execute("UPDATE evidence SET quote_hash = encode(sha256(convert_to(quote_text, 'UTF8')), 'hex') WHERE quote_hash IS NULL")
    op.create_table(
        "event_merge_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("operator", sa.String(200), nullable=False),
        sa.Column("before_state", postgresql.JSONB(), nullable=False),
        sa.Column("reverted_at", sa.DateTime(timezone=True)),
        sa.Column("reverted_by", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["target_event_id"], ["events.id"]),
    )
    op.create_index("ix_event_merge_log_source", "event_merge_log", ["source_event_id"])
    op.create_table(
        "event_date_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("before_date", sa.Date()),
        sa.Column("before_precision", sa.String(12), nullable=False),
        sa.Column("before_basis", sa.String(32), nullable=False),
        sa.Column("after_date", sa.Date(), nullable=False),
        sa.Column("after_precision", sa.String(12), nullable=False),
        sa.Column("after_basis", sa.String(32), nullable=False),
        sa.Column("operator", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"]),
    )


def downgrade() -> None:
    active_merge = op.get_bind().execute(
        sa.text("SELECT 1 FROM event_merge_log WHERE reverted_at IS NULL LIMIT 1")
    ).scalar()
    if active_merge is not None:
        raise RuntimeError("refusing lossy downgrade while active event merges exist")
    op.drop_table("event_date_audit_log")
    op.drop_index("ix_event_merge_log_source", table_name="event_merge_log")
    op.drop_table("event_merge_log")
    for name in ("support_type", "quote_hash", "claim_text", "claim_key"):
        op.drop_column("evidence", name)
    op.drop_constraint("ck_events_date_semantics", "events", type_="check")
    op.drop_constraint("fk_events_merged_into", "events", type_="foreignkey")
    op.drop_constraint("fk_events_date_evidence", "events", type_="foreignkey")
    for name in ("merged_into_event_id", "date_evidence_id", "date_basis"):
        op.drop_column("events", name)
