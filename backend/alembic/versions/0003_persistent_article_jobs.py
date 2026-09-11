"""Split feed discovery from persistent article fetching.

Workers must be stopped while upgrading or downgrading so no lease observes
mixed stage semantics.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_persistent_article_jobs"
down_revision: str | None = "0002_ingest_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE ingest_jobs SET stage = 'feed_discovery' WHERE stage = 'rss_fetch'")
    op.add_column("ingest_jobs", sa.Column("job_key", sa.String(160)))
    op.execute("UPDATE ingest_jobs SET job_key = 'legacy:' || id::text")
    op.alter_column("ingest_jobs", "job_key", nullable=False)
    op.create_unique_constraint("uq_ingest_jobs_job_key", "ingest_jobs", ["job_key"])
    op.create_table(
        "article_discoveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingest_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("published", sa.Text()),
        sa.Column(
            "article_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "run_id", "source_id", "canonical_url", name="uq_discovery_run_source_url"
        ),
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE ingest_jobs
        SET state = 'cancelled', lease_owner = NULL, lease_until = NULL
        WHERE stage = 'article_fetch'
          AND state IN ('queued', 'retry_wait', 'running')
        """
    )
    op.execute("UPDATE ingest_jobs SET stage = 'rss_fetch' WHERE stage = 'feed_discovery'")
    op.drop_table("article_discoveries")
    op.drop_constraint("uq_ingest_jobs_job_key", "ingest_jobs", type_="unique")
    op.drop_column("ingest_jobs", "job_key")
