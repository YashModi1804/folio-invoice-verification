"""Initial jobs, extraction snapshot, audit and review storage.

Extraction and check snapshots are immutable JSON within the job aggregate.
"""

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None


def upgrade():
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("idempotency_key", sa.String(128), unique=True, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(50), nullable=False),
        sa.Column("page_count", sa.Integer, nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("sample", sa.String(30)),
        sa.Column("error", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("result", sa.JSON),
    )
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("processing_jobs.id"), nullable=False),
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("details", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_job_id", "audit_events", ["job_id"])
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey("processing_jobs.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("note", sa.String(1000), nullable=False),
        sa.Column("corrected_invoice", sa.JSON),
        sa.Column("checks", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("review_decisions")
    op.drop_table("audit_events")
    op.drop_table("processing_jobs")
