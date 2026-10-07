"""Store source documents in the database for single-service deployments."""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"


def upgrade():
    op.create_table(
        "document_sources",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["processing_jobs.id"]),
        sa.PrimaryKeyConstraint("job_id"),
    )


def downgrade():
    op.drop_table("document_sources")
