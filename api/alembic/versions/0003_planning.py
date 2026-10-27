"""User-owned planning aggregates.

Revision ID: 0003_planning
Revises: 0002_auth
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_planning"
down_revision: str | None = "0002_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "planning_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind <> 'goal' OR COALESCE("
            "json_array_length(payload -> 'actions') BETWEEN 1 AND 5, false)",
            name="goal_actions_cap",
        ),
    )
    op.create_index("ix_planning_records_user_id", "planning_records", ["user_id"])
    op.create_index("ix_planning_records_kind", "planning_records", ["kind"])


def downgrade() -> None:
    op.drop_table("planning_records")
