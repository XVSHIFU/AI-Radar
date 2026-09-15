"""Versioned full text, embeddings and immutable retrieval snapshots."""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_retrieval"
down_revision: str | None = "0008_data_quality"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TOKEN = re.compile(r"[a-z0-9]+(?:[._+-][a-z0-9]+)*|[\u3400-\u9fff]+", re.IGNORECASE)


def _search_document(*parts: str) -> str:
    """Frozen cjk-bigram-v1 implementation; migrations must remain self-contained."""
    tokens: list[str] = []
    for raw in parts:
        for match in _TOKEN.findall(raw.casefold()):
            if "\u3400" <= match[0] <= "\u9fff":
                chars = list(match)
                tokens.extend(
                    chars
                    if len(chars) == 1
                    else ["".join(chars[i : i + 2]) for i in range(len(chars) - 1)]
                )
            else:
                tokens.append(match)
    return " ".join(dict.fromkeys(tokens))


def upgrade() -> None:
    op.add_column(
        "events", sa.Column("search_document", sa.Text(), nullable=False, server_default="")
    )
    op.add_column(
        "events",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', coalesce(search_document, ''))", persisted=True),
        ),
    )
    op.add_column(
        "events",
        sa.Column(
            "search_config_version", sa.String(32), nullable=False, server_default="cjk-bigram-v1"
        ),
    )
    op.add_column("events", sa.Column("search_indexed_at", sa.DateTime(timezone=True)))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, title_zh, summary_zh FROM events")).mappings()
    for row in rows:
        bind.execute(
            sa.text(
                "UPDATE events SET search_document=:document, search_indexed_at=now() WHERE id=:id"
            ),
            {"id": row["id"], "document": _search_document(row["title_zh"], row["summary_zh"])},
        )
    op.create_index("ix_events_search_vector", "events", ["search_vector"], postgresql_using="gin")
    op.create_table(
        "embedding_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("revision", sa.String(200), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("normalize", sa.Boolean(), nullable=False),
        sa.Column("input_template_version", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("dimension = 1024", name="ck_embedding_profile_v1_dimension"),
        sa.UniqueConstraint(
            "provider",
            "model_id",
            "revision",
            "normalize",
            "input_template_version",
            name="uq_embedding_profile_identity",
        ),
    )
    op.create_index(
        "uq_embedding_profile_active",
        "embedding_profiles",
        ["active"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.execute("""CREATE TABLE event_embeddings_v1 (
        event_id uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        profile_id uuid NOT NULL REFERENCES embedding_profiles(id) ON DELETE CASCADE,
        input_hash varchar(64) NOT NULL, event_content_version integer NOT NULL,
        embedding vector(1024), status varchar(24) NOT NULL, indexed_at timestamptz,
        PRIMARY KEY (event_id, profile_id),
        CONSTRAINT ck_event_embedding_state CHECK (
          (status = 'ready' AND embedding IS NOT NULL AND indexed_at IS NOT NULL)
          OR (status IN ('pending','failed','stale') AND embedding IS NULL))
    )""")
    op.create_index(
        "ix_event_embeddings_profile_status", "event_embeddings_v1", ["profile_id", "status"]
    )
    op.create_table(
        "retrieval_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filters_hash", sa.String(64), nullable=False),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("total = jsonb_array_length(items)", name="ck_retrieval_snapshot_total"),
    )
    op.create_index("ix_retrieval_snapshots_expires_at", "retrieval_snapshots", ["expires_at"])


def downgrade() -> None:
    op.drop_table("retrieval_snapshots")
    op.drop_table("event_embeddings_v1")
    op.drop_table("embedding_profiles")
    op.drop_index("ix_events_search_vector", table_name="events")
    for column in (
        "search_indexed_at",
        "search_config_version",
        "search_vector",
        "search_document",
    ):
        op.drop_column("events", column)
