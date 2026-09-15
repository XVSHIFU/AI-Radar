"""Allow forgetting expired IP keys without discarding idempotency or usage."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_public_quota_retention"
down_revision: str | None = "0012_research_model_calls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("public_ask_requests", "ip_hash", existing_type=sa.String(64), nullable=True)


def downgrade() -> None:
    # Expired IPs cannot be recovered. An empty, non-HMAC sentinel lets legacy code
    # read the row while retaining its owner/request idempotency and accounting.
    op.execute("UPDATE public_ask_requests SET ip_hash = '' WHERE ip_hash IS NULL")
    op.alter_column("public_ask_requests", "ip_hash", existing_type=sa.String(64), nullable=False)
