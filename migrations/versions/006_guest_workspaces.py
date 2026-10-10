"""Give guests isolated workspaces without changing operator records."""

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"


def upgrade():
    op.create_table(
        "guest_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_guest_sessions_token_hash", "guest_sessions", ["token_hash"])
    op.create_table(
        "guest_upload_usage",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "guest_id", sa.String(length=36), sa.ForeignKey("guest_sessions.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_guest_upload_usage_guest_id", "guest_upload_usage", ["guest_id"])
    op.create_index("ix_guest_upload_usage_created_at", "guest_upload_usage", ["created_at"])
    op.add_column(
        "processing_jobs",
        sa.Column("workspace_id", sa.String(length=36), nullable=False, server_default="operator"),
    )
    op.create_index("ix_processing_jobs_workspace_id", "processing_jobs", ["workspace_id"])


def downgrade():
    op.drop_index("ix_processing_jobs_workspace_id", table_name="processing_jobs")
    op.drop_column("processing_jobs", "workspace_id")
    op.drop_index("ix_guest_upload_usage_created_at", table_name="guest_upload_usage")
    op.drop_index("ix_guest_upload_usage_guest_id", table_name="guest_upload_usage")
    op.drop_table("guest_upload_usage")
    op.drop_index("ix_guest_sessions_token_hash", table_name="guest_sessions")
    op.drop_table("guest_sessions")
