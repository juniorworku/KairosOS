"""Explicit multi-calendar selection and owned-event write consent."""

import sqlalchemy as sa

from alembic import op

revision = "0006_multi_calendar"
down_revision = "0005_google_event_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calendar_connections",
        sa.Column("editing_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "calendar_connections",
        sa.Column("selection_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for name in ("calendars_access", "edit_access"):
        op.add_column(
            "calendar_oauth_states",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    op.create_table(
        "calendar_selections",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("calendar_id", sa.String(512), nullable=False),
        sa.Column("metadata_enc", sa.LargeBinary(), nullable=False),
        sa.Column("access_role", sa.String(40), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("user_id", "calendar_id"),
    )
    op.create_index("ix_calendar_selections_user_id", "calendar_selections", ["user_id"])


def downgrade() -> None:
    op.drop_table("calendar_selections")
    for name in ("calendars_access", "edit_access"):
        op.drop_column("calendar_oauth_states", name)
    op.drop_column("calendar_connections", "selection_enabled")
    op.drop_column("calendar_connections", "editing_enabled")
