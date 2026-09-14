"""Persist upstream rate-limit cooldown across jobs and worker restarts."""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_source_cooldown"
down_revision: str | None = "0004_candidate_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("cooldown_until", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("sources", "cooldown_until")
