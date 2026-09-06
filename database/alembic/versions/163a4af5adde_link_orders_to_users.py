"""link orders to users

Revision ID: 163a4af5adde
Revises: 9ba1078ca3c0
Create Date: 2026-08-31 17:48:26.326452

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '163a4af5adde'
down_revision: Union[str, Sequence[str], None] = '9ba1078ca3c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add the column as nullable while existing orders are backfilled.
    op.add_column('orders', sa.Column('user_id', sa.UUID(), nullable=True))

    connection = op.get_bind()
    order_count = connection.execute(sa.text("SELECT count(*) FROM orders")).scalar_one()
    if order_count:
        owner_id = connection.execute(
            sa.text('SELECT id FROM "Users" WHERE username = :username'),
            {"username": "Vedika12311"},
        ).scalar_one()
        connection.execute(
            sa.text("UPDATE orders SET user_id = :user_id WHERE user_id IS NULL"),
            {"user_id": owner_id},
        )

    op.alter_column('orders', 'user_id', nullable=False)
    op.create_foreign_key(
        'fk_orders_user_id_users', 'orders', 'Users', ['user_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_orders_user_id_users', 'orders', type_='foreignkey')
    op.drop_column('orders', 'user_id')
