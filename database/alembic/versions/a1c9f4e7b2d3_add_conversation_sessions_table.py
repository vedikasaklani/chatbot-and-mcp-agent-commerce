"""add conversation_sessions table

Revision ID: a1c9f4e7b2d3
Revises: 5c2f6f8c1d4a
Create Date: 2026-09-05 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c9f4e7b2d3"
down_revision: Union[str, Sequence[str], None] = "5c2f6f8c1d4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "conversation_sessions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["Users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("conversation_sessions")
