"""add decision record to orders

Revision ID: 5c2f6f8c1d4a
Revises: 4f7c2d1a9b6e
Create Date: 2026-09-04 16:35:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5c2f6f8c1d4a"
down_revision: Union[str, Sequence[str], None] = "4f7c2d1a9b6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the decision record column when it is missing."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("orders")}
    if "decision_record" not in columns:
        op.add_column("orders", sa.Column("decision_record", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove the decision record column when it exists."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("orders")}
    if "decision_record" in columns:
        op.drop_column("orders", "decision_record")
