"""ntfy subscriptions

Revision ID: c3a8f21b4e5d
Revises: b9e3f53b7d64
Create Date: 2026-01-18 01:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3a8f21b4e5d"
down_revision: Union[str, None] = "b9e3f53b7d64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ntfy_subscriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ntfy_topic", sa.Text(), nullable=False),
        sa.Column("from_asset", sa.Text(), nullable=False),
        sa.Column("to_asset", sa.Text(), nullable=False),
        sa.Column("fee_threshold", sa.DECIMAL(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ntfy_subscriptions")
