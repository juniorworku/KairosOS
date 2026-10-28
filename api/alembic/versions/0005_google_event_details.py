"""Explicit event-detail consent and encrypted primary-calendar occurrence cache.

Revision ID: 0005_google_event_details
Revises: 0004_integrations
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0005_google_event_details"
down_revision: str | None = "0004_integrations"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "calendar_connections",
        sa.Column("details_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for name in ("details_from", "details_to"):
        op.add_column("calendar_connections", sa.Column(name, sa.Date()))
    op.add_column("calendar_connections", sa.Column("details_timezone", sa.String(80)))
    op.add_column(
        "calendar_connections", sa.Column("details_synced_at", sa.DateTime(timezone=True))
    )
    op.add_column("calendar_connections", sa.Column("details_error", sa.String(300)))
    op.add_column(
        "calendar_oauth_states",
        sa.Column("details_access", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "google_event_cache",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("calendar_id", sa.String(512), nullable=False),
        sa.Column("provider_event_id", sa.String(1024), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("recurring", sa.Boolean(), nullable=False),
        sa.Column("occurrence_date", sa.Date()),
        sa.Column("details_enc", sa.LargeBinary(), nullable=False),
        sa.UniqueConstraint("user_id", "calendar_id", "provider_event_id"),
    )
    op.create_index("ix_google_event_cache_user_id", "google_event_cache", ["user_id"])
    op.create_index(
        "ix_google_event_cache_owner_time", "google_event_cache", ["user_id", "start_at", "end_at"]
    )
    op.create_index(
        "ix_google_event_cache_owner_date",
        "google_event_cache",
        ["user_id", "start_date", "end_date"],
    )


def downgrade() -> None:
    op.drop_table("google_event_cache")
    op.drop_column("calendar_oauth_states", "details_access")
    for name in (
        "details_error",
        "details_synced_at",
        "details_timezone",
        "details_to",
        "details_from",
        "details_enabled",
    ):
        op.drop_column("calendar_connections", name)
