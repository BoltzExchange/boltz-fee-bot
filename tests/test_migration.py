"""Tests for database migration backward compatibility."""

import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from db import (
    Subscription,
    add_subscription,
    get_subscriptions,
    PLATFORM_TELEGRAM,
    PLATFORM_SIMPLEX,
)


@pytest.mark.db
@pytest.mark.asyncio(loop_scope="session")
async def test_migration_preserves_existing_telegram_subscriptions(
    db_session: AsyncSession,
):
    """Verify existing Telegram subscriptions work with new schema."""
    # Create a Telegram subscription (simulating pre-migration data)
    telegram_sub = Subscription(
        platform=PLATFORM_TELEGRAM,
        chat_id=123456789,
        from_asset="BTC",
        to_asset="LN",
        fee_threshold=Decimal("0.5"),
    )
    assert await add_subscription(db_session, telegram_sub)

    # Verify retrieval works
    subscriptions = await get_subscriptions(db_session, chat_id=123456789)
    assert len(subscriptions) >= 1

    found = False
    for sub in subscriptions:
        if (
            sub.chat_id == 123456789
            and sub.from_asset == "BTC"
            and sub.to_asset == "LN"
        ):
            assert sub.platform == PLATFORM_TELEGRAM
            assert sub.platform_chat_id is None
            found = True
            break

    assert found, "Telegram subscription not found"


@pytest.mark.db
@pytest.mark.asyncio(loop_scope="session")
async def test_migration_allows_simplex_subscriptions(db_session: AsyncSession):
    """Verify new SimpleX subscriptions can be created with platform_chat_id."""
    simplex_sub = Subscription(
        platform=PLATFORM_SIMPLEX,
        platform_chat_id="contact_abc123",
        chat_id=None,
        from_asset="BTC",
        to_asset="L-BTC",
        fee_threshold=Decimal("0.5"),
    )
    assert await add_subscription(db_session, simplex_sub)

    # Verify retrieval by platform_chat_id
    subscriptions = await get_subscriptions(
        db_session, platform=PLATFORM_SIMPLEX, platform_chat_id="contact_abc123"
    )
    assert len(subscriptions) >= 1

    found = False
    for sub in subscriptions:
        if sub.platform_chat_id == "contact_abc123":
            assert sub.platform == PLATFORM_SIMPLEX
            assert sub.chat_id is None
            found = True
            break

    assert found, "SimpleX subscription not found"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_recipient_id_returns_correct_id_for_telegram():
    """Verify get_recipient_id() returns chat_id for Telegram."""
    telegram_sub = Subscription(
        platform=PLATFORM_TELEGRAM,
        chat_id=987654321,
        platform_chat_id=None,
        from_asset="BTC",
        to_asset="LN",
        fee_threshold=Decimal("0.5"),
    )
    assert telegram_sub.get_recipient_id() == "987654321"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_recipient_id_returns_correct_id_for_simplex():
    """Verify get_recipient_id() returns platform_chat_id for SimpleX."""
    simplex_sub = Subscription(
        platform=PLATFORM_SIMPLEX,
        chat_id=None,
        platform_chat_id="contact_xyz789",
        from_asset="BTC",
        to_asset="LN",
        fee_threshold=Decimal("0.5"),
    )
    assert simplex_sub.get_recipient_id() == "contact_xyz789"


@pytest.mark.db
@pytest.mark.asyncio(loop_scope="session")
async def test_subscriptions_coexist(db_session: AsyncSession):
    """Verify Telegram and SimpleX subscriptions can coexist."""
    # Create Telegram subscription
    telegram_sub = Subscription(
        platform=PLATFORM_TELEGRAM,
        chat_id=111222333,
        from_asset="LN",
        to_asset="BTC",
        fee_threshold=Decimal("0.1"),
    )
    await add_subscription(db_session, telegram_sub)

    # Create SimpleX subscription
    simplex_sub = Subscription(
        platform=PLATFORM_SIMPLEX,
        platform_chat_id="contact_coexist",
        from_asset="LN",
        to_asset="BTC",
        fee_threshold=Decimal("0.1"),
    )
    await add_subscription(db_session, simplex_sub)

    # Get all subscriptions
    all_subs = await get_subscriptions(db_session)

    platforms = set(s.platform for s in all_subs)
    assert PLATFORM_TELEGRAM in platforms
    assert PLATFORM_SIMPLEX in platforms


@pytest.mark.asyncio(loop_scope="session")
async def test_telegram_subscription_default_platform():
    """Verify Telegram subscriptions default to 'telegram' platform."""
    sub = Subscription(
        chat_id=999888777,
        from_asset="BTC",
        to_asset="LN",
        fee_threshold=Decimal("0.05"),
    )
    # Default should be 'telegram'
    assert sub.platform == PLATFORM_TELEGRAM
