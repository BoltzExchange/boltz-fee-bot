"""add multiplatform support

Revision ID: c7f2a8d91e23
Revises: b9e3f53b7d64
Create Date: 2026-01-19 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c7f2a8d91e23"
down_revision: Union[str, None] = "b9e3f53b7d64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add platform column with default 'telegram' for existing rows
    # This is backward-compatible: all existing subscriptions get tagged as telegram
    op.add_column(
        "subscriptions",
        sa.Column(
            "platform",
            sa.Text(),
            nullable=False,
            server_default="telegram",
        ),
    )

    # Add platform_chat_id for non-Telegram platforms (nullable)
    # Telegram continues to use chat_id (BigInteger), other platforms use this
    op.add_column(
        "subscriptions",
        sa.Column(
            "platform_chat_id",
            sa.Text(),
            nullable=True,
        ),
    )

    # Make chat_id nullable for non-Telegram platforms
    # Existing Telegram subscriptions keep their chat_id values
    op.alter_column(
        "subscriptions",
        "chat_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    # Delete non-Telegram subscriptions that have NULL chat_id
    # This is required before we can set chat_id to NOT NULL
    op.execute(
        "DELETE FROM subscriptions WHERE platform != 'telegram' OR platform IS NULL"
    )

    # Now safe to restore chat_id to non-nullable
    op.alter_column(
        "subscriptions",
        "chat_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )

    # Remove the new columns
    op.drop_column("subscriptions", "platform_chat_id")
    op.drop_column("subscriptions", "platform")
