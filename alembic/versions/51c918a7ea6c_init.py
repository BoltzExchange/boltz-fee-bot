"""init

Revision ID: 51c918a7ea6c
Revises:
Create Date: 2025-02-04 08:16:56.633409

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "51c918a7ea6c"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "previous",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
        if_not_exists=True,
    )
    op.create_table(
        "subscribers",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("chat_id"),
        sa.UniqueConstraint("chat_id"),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("subscribers")
    op.drop_table("previous")
