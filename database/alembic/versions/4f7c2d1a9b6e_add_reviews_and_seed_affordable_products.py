"""add reviews and seed affordable products

Revision ID: 4f7c2d1a9b6e
Revises: 163a4af5adde, c2b4b9ff0f91
Create Date: 2026-09-03 05:04:25.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f7c2d1a9b6e"
down_revision: Union[str, Sequence[str], None] = (
    "163a4af5adde",
    "c2b4b9ff0f91",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create reviews and seed reviews for products below ₹10,000."""
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["Products.pid"]),
        sa.ForeignKeyConstraint(["user_id"], ["Users.id"]),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO reviews (product_id, user_id, rating, text, created_at)
            SELECT products.pid, NULL, seed.rating, seed.review_text, CURRENT_TIMESTAMP
            FROM "Products" AS products
            CROSS JOIN (
                VALUES
                    (5, 'Excellent quality and great value for money.'),
                    (4, 'Good product and arrived as expected.'),
                    (4, 'Useful, reliable, and worth the price.')
            ) AS seed(rating, review_text)
            WHERE products.price < 10000
            """
        )
    )


def downgrade() -> None:
    """Drop reviews and their seeded data."""
    op.drop_table("reviews")
