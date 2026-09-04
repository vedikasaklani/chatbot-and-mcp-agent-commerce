"""making id a uuid key

Revision ID: 0b88dda0ece9
Revises: ce11ede30bc7
Create Date: 2026-08-31 00:02:47.411605

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b88dda0ece9'
down_revision: Union[str, Sequence[str], None] = 'ce11ede30bc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert existing integer IDs to deterministic UUIDs."""
    # PostgreSQL cannot implicitly cast an integer (or its serial default) to
    # UUID. Padding the old integer preserves every existing ID's identity.
    op.alter_column(
        "Users",
        "id",
        existing_type=sa.INTEGER(),
        existing_nullable=False,
        server_default=None,
    )
    op.alter_column('Users', 'id',
               existing_type=sa.INTEGER(),
               type_=sa.UUID(),
               existing_nullable=False,
               postgresql_using="lpad(id::text, 32, '0')::uuid")


def downgrade() -> None:
    """UUID values cannot safely be converted back to integer IDs."""
    raise NotImplementedError("Downgrading User IDs from UUID to integer is unsafe")
