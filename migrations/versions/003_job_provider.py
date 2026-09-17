"""Pin routing provenance instead of relabeling history with current settings."""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"


def upgrade():
    op.add_column(
        "processing_jobs",
        sa.Column("provider", sa.String(20), nullable=False, server_default="fixture"),
    )
    jobs = sa.table(
        "processing_jobs",
        sa.column("id"),
        sa.column("sample"),
        sa.column("result", sa.JSON),
        sa.column("provider"),
    )
    events = sa.table(
        "audit_events", sa.column("job_id"), sa.column("event"), sa.column("details", sa.JSON)
    )
    connection = op.get_bind()
    for job in connection.execute(sa.select(jobs)).mappings():
        provider = "fixture"
        if not job["sample"]:
            event = connection.execute(
                sa.select(events.c.details).where(
                    events.c.job_id == job["id"], events.c.event == "UPLOADED"
                )
            ).scalar()
            provider = (
                (job["result"] or {}).get("telemetry", {}).get("provider")
                or (event or {}).get("mode")
                or "gemini"
            )
        connection.execute(jobs.update().where(jobs.c.id == job["id"]).values(provider=provider))


def downgrade():
    op.drop_column("processing_jobs", "provider")
