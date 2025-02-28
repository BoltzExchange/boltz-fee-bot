"""custom fee config

Revision ID: b9e3f53b7d64
Revises: 51c918a7ea6c
Create Date: 2025-02-04 08:18:31.589252

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b9e3f53b7d64"
down_revision: Union[str, None] = "51c918a7ea6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("subscribers", "subscriptions")

    op.drop_constraint("subscribers_pkey", "subscriptions", type_="primary")
    op.add_column(
        "subscriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
    )

    op.add_column(
        "subscriptions",
        sa.Column("fee_threshold", sa.DECIMAL(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "subscriptions",
        sa.Column("from_asset", sa.Text(), nullable=False, server_default="BTC"),
    )
    op.add_column(
        "subscriptions",
        sa.Column("to_asset", sa.Text(), nullable=False, server_default="LN"),
    )
    op.alter_column("subscriptions", "fee_threshold", server_default=None)
    op.alter_column("subscriptions", "from_asset", server_default=None)
    op.alter_column("subscriptions", "to_asset", server_default=None)

    # the sequence is still here because chat_id was the initial primary_key
    op.alter_column("subscriptions", "chat_id", server_default=None)
    op.execute("DROP SEQUENCE subscribers_chat_id_seq")


def downgrade() -> None:
    pass
