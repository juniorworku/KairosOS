"""Calendar, extension pairing, and coaching usage records.

Revision ID: 0004_integrations
Revises: 0003_planning
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0004_integrations"
down_revision: str | None = "0003_planning"
branch_labels: str | None = None
depends_on: str | None = None


def identity() -> list[sa.Column[str]]:
    return [
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "calendar_connections",
        *identity(),
        sa.Column("token_enc", sa.LargeBinary(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("app_calendar_id", sa.String(512)),
        sa.Column("sync_token", sa.String(2048)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "calendar_busy_intervals",
        *identity(),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_calendar_busy_intervals_user_id", "calendar_busy_intervals", ["user_id"])
    op.create_table(
        "calendar_oauth_states",
        *identity(),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("verifier", sa.String(128), nullable=False),
        sa.Column("write_access", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "extension_pair_codes",
        *identity(),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "extension_tokens",
        *identity(),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_extension_tokens_user_id", "extension_tokens", ["user_id"])
    op.create_table(
        "ai_calls",
        *identity(),
        sa.Column("task", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_calls_user_id", "ai_calls", ["user_id"])


def downgrade() -> None:
    for name in [
        "ai_calls",
        "extension_tokens",
        "extension_pair_codes",
        "calendar_oauth_states",
        "calendar_busy_intervals",
        "calendar_connections",
    ]:
        op.drop_table(name)
