"""Track worker readiness independently from API liveness."""

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"


def upgrade():
    op.create_table(
        "worker_heartbeats",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("worker_heartbeats")
