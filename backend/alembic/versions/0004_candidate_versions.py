"""Bind new candidates to immutable article versions.

Legacy candidates remain unbound and require refetch: their historical version
cannot be inferred safely from a URL. Downgrade refuses lossy deduplication.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_candidate_versions"
down_revision: str | None = "0003_persistent_article_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "article_candidates",
        sa.Column(
            "article_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_candidate_article_version",
        "article_candidates",
        "article_versions",
        ["article_version_id"],
        ["id"],
    )
    op.drop_constraint("uq_candidate_source_url", "article_candidates", type_="unique")
    op.create_unique_constraint(
        "uq_candidate_source_version",
        "article_candidates",
        ["source_id", "article_version_id"],
    )
    op.execute(
        "UPDATE article_candidates SET status = 'needs_refetch' "
        "WHERE article_version_id IS NULL AND status = 'needs_review'"
    )


def downgrade() -> None:
    # Creating the old constraint first fails atomically if multiple versions
    # share a URL. Operators must archive/resolve these explicitly before rollback.
    op.create_unique_constraint(
        "uq_candidate_source_url",
        "article_candidates",
        ["source_id", "canonical_url"],
    )
    op.drop_constraint("uq_candidate_source_version", "article_candidates", type_="unique")
    op.drop_constraint("fk_candidate_article_version", "article_candidates", type_="foreignkey")
    op.drop_column("article_candidates", "article_version_id")
