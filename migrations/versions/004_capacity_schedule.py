"""Persist deferred provider-capacity retries."""

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"


def upgrade():
    op.add_column(
        "processing_jobs",
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_processing_jobs_not_before", "processing_jobs", ["not_before"])


def downgrade():
    op.drop_index("ix_processing_jobs_not_before", table_name="processing_jobs")
    op.drop_column("processing_jobs", "not_before")
