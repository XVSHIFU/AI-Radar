"""Publish raw articles separately from curated events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0015_article_feed"
down_revision: str | None = "0014_content_workbench"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("title", sa.Text()))
    op.add_column("articles", sa.Column("excerpt", sa.Text()))
    op.add_column("articles", sa.Column("published_at", sa.DateTime(timezone=True)))
    op.add_column("articles", sa.Column("ingested_at", sa.DateTime(timezone=True)))
    op.add_column("articles", sa.Column("status", sa.String(16), nullable=False, server_default="legacy"))
    op.add_column("articles", sa.Column("category", sa.String(32)))
    op.add_column("articles", sa.Column("current_version_id", UUID(as_uuid=True)))
    op.add_column("articles", sa.Column("content_hash", sa.String(64)))
    op.add_column("articles", sa.Column("duplicate_of_id", UUID(as_uuid=True)))
    op.create_index("ix_articles_feed", "articles", ["status", "published_at", "ingested_at"])
    op.create_index("ix_articles_content_hash", "articles", ["content_hash"])
    for table in ("articles", "article_versions", "event_articles", "sources"):
        op.execute(f"CREATE TRIGGER trg_{table}_feed_revision AFTER INSERT OR UPDATE OR DELETE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION bump_retrieval_data_revision()")


def downgrade() -> None:
    for table in ("articles", "article_versions", "event_articles", "sources"):
        op.execute(f"DROP TRIGGER trg_{table}_feed_revision ON {table}")
    op.drop_index("ix_articles_content_hash", "articles")
    op.drop_index("ix_articles_feed", "articles")
    for name in ("duplicate_of_id", "content_hash", "current_version_id", "category", "status", "ingested_at", "published_at", "excerpt", "title"):
        op.drop_column("articles", name)
