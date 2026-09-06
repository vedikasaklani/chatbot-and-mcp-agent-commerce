"""fix users auth schema

Revision ID: c2b4b9ff0f91
Revises: 90e9016d6e90
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2b4b9ff0f91"
down_revision: Union[str, Sequence[str], None] = "90e9016d6e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("Users")}

    if "email" not in columns:
        op.add_column("Users", sa.Column("email", sa.String(), nullable=True))
    if "hashed_password" not in columns:
        op.add_column("Users", sa.Column("hashed_password", sa.String(), nullable=True))
    if "username" not in columns:
        op.add_column("Users", sa.Column("username", sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("Users")}

    if "username" in columns:
        op.drop_column("Users", "username")
    if "hashed_password" in columns:
        op.drop_column("Users", "hashed_password")
    if "email" in columns:
        op.drop_column("Users", "email")
