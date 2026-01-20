import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot import check_subscription, check_fees
from db import Subscription, PLATFORM_TELEGRAM, PLATFORM_SIMPLEX


# Test data for Telegram subscriptions (backward compatible)
TELEGRAM_TEST_CASES = [
    (
        {"BTC": {"LN": 1.2}},
        {"BTC": {"LN": 1.0}},
        "BTC",
        "LN",
        1.0,
        True,
        "fee exactly at threshold",
    ),
    (
        {"BTC": {"LN": 0.8}},
        {"BTC": {"LN": 1.2}},
        "BTC",
        "LN",
        1.0,
        True,
        "fee drops below threshold",
    ),
    (
        {"LN": {"BTC": 1.2}},
        {"LN": {"BTC": 0.8}},
        "LN",
        "BTC",
        1.0,
        True,
        "LN to BTC fee goes above threshold",
    ),
    (
        {"LN": {"BTC": 0.8}},
        {"LN": {"BTC": 1.0}},
        "LN",
        "BTC",
        1.0,
        False,
        "fee goes back to threshold",
    ),
    (
        {"L-BTC": {"RBTC": 1.5}},
        {"L-BTC": {"RBTC": 1.3}},
        "L-BTC",
        "RBTC",
        1.0,
        False,
        "L-BTC to RBTC fee changes but doesn't cross threshold",
    ),
    (
        {"RBTC": {"LN": 1.0}},
        {"RBTC": {"LN": 1.0}},
        "RBTC",
        "LN",
        1.0,
        False,
        "RBTC to LN fee equals threshold",
    ),
    (
        {},
        {"L-BTC": {"BTC": 1.0}},
        "L-BTC",
        "BTC",
        1.0,
        False,
        "missing fees in current",
    ),
    (
        {"RBTC": {"L-BTC": 1.0}},
        {},
        "RBTC",
        "L-BTC",
        1.0,
        False,
        "missing fees in previous",
    ),
    (
        {"LN": {}},
        {"LN": {"RBTC": 1.0}},
        "LN",
        "RBTC",
        1.0,
        False,
        "missing to_asset in current",
    ),
]


@pytest.mark.parametrize(
    "current_fees, previous_fees, from_asset, to_asset, threshold, expected, test_description",
    TELEGRAM_TEST_CASES,
)
def test_check_subscription_telegram(
    current_fees,
    previous_fees,
    from_asset,
    to_asset,
    threshold,
    expected,
    test_description,
):
    """Test check_subscription with Telegram subscriptions (backward compatible)."""
    subscription = Subscription(
        platform=PLATFORM_TELEGRAM,
        chat_id=123,
        from_asset=from_asset,
        to_asset=to_asset,
        fee_threshold=threshold,
    )

    result = check_subscription(current_fees, previous_fees, subscription)
    assert result == expected, f"Failed case: {test_description}"


# Test data for SimpleX subscriptions
SIMPLEX_TEST_CASES = [
    (
        {"BTC": {"LN": 0.8}},
        {"BTC": {"LN": 1.2}},
        "BTC",
        "LN",
        1.0,
        True,
        "SimpleX: fee drops below threshold",
    ),
    (
        {"LN": {"BTC": 1.2}},
        {"LN": {"BTC": 0.8}},
        "LN",
        "BTC",
        1.0,
        True,
        "SimpleX: fee goes above threshold",
    ),
    (
        {"L-BTC": {"RBTC": 1.5}},
        {"L-BTC": {"RBTC": 1.3}},
        "L-BTC",
        "RBTC",
        1.0,
        False,
        "SimpleX: fee changes but doesn't cross threshold",
    ),
]


@pytest.mark.parametrize(
    "current_fees, previous_fees, from_asset, to_asset, threshold, expected, test_description",
    SIMPLEX_TEST_CASES,
)
def test_check_subscription_simplex(
    current_fees,
    previous_fees,
    from_asset,
    to_asset,
    threshold,
    expected,
    test_description,
):
    """Test check_subscription with SimpleX subscriptions."""
    subscription = Subscription(
        platform=PLATFORM_SIMPLEX,
        platform_chat_id="contact_test",
        from_asset=from_asset,
        to_asset=to_asset,
        fee_threshold=threshold,
    )

    result = check_subscription(current_fees, previous_fees, subscription)
    assert result == expected, f"Failed case: {test_description}"


# Keep backward compatible test name
@pytest.mark.parametrize(
    "current_fees, previous_fees, from_asset, to_asset, threshold, expected, test_description",
    TELEGRAM_TEST_CASES,
)
def test_check_subscription(
    current_fees,
    previous_fees,
    from_asset,
    to_asset,
    threshold,
    expected,
    test_description,
):
    """Backward compatible test - uses Telegram by default."""
    subscription = Subscription(
        chat_id=123, from_asset=from_asset, to_asset=to_asset, fee_threshold=threshold
    )

    result = check_subscription(current_fees, previous_fees, subscription)
    assert result == expected, f"Failed case: {test_description}"


@pytest.mark.asyncio(loop_scope="session")
async def test_check_fees_telegram(db_session: AsyncSession):
    """Test check_fees with Telegram subscriptions."""
    current_fees = {"BTC": {"LN": 1.2}}
    subscriptions = [
        Subscription(
            platform=PLATFORM_TELEGRAM,
            chat_id=123,
            from_asset="BTC",
            to_asset="LN",
            fee_threshold=1.0,
        ),
        Subscription(
            platform=PLATFORM_TELEGRAM,
            chat_id=123,
            from_asset="BTC",
            to_asset="LN",
            fee_threshold=0.5,
        ),
    ]
    db_session.add_all(subscriptions)
    await db_session.commit()
    result = await check_fees(db_session, current_fees)
    assert len(result) == 0

    current_fees = {"BTC": {"LN": 0.8}}
    result = await check_fees(db_session, current_fees)
    assert result[0].id == subscriptions[0].id, "Failed to check fees"


@pytest.mark.asyncio(loop_scope="session")
async def test_check_fees_simplex(db_session: AsyncSession):
    """Test check_fees with SimpleX subscriptions."""
    current_fees = {"L-BTC": {"BTC": 1.2}}
    subscriptions = [
        Subscription(
            platform=PLATFORM_SIMPLEX,
            platform_chat_id="contact_simplex_1",
            from_asset="L-BTC",
            to_asset="BTC",
            fee_threshold=1.0,
        ),
    ]
    db_session.add_all(subscriptions)
    await db_session.commit()

    # Initial check - no previous, no notifications
    result = await check_fees(db_session, current_fees)
    assert len(result) == 0

    # Fee drops below threshold - should notify
    current_fees = {"L-BTC": {"BTC": 0.8}}
    result = await check_fees(db_session, current_fees)
    simplex_results = [s for s in result if s.platform == PLATFORM_SIMPLEX]
    assert len(simplex_results) >= 1


@pytest.mark.asyncio(loop_scope="session")
async def test_check_fees_mixed_platforms(db_session: AsyncSession):
    """Test check_fees with both Telegram and SimpleX subscriptions."""
    current_fees = {"RBTC": {"LN": 1.2}}
    subscriptions = [
        Subscription(
            platform=PLATFORM_TELEGRAM,
            chat_id=789,
            from_asset="RBTC",
            to_asset="LN",
            fee_threshold=1.0,
        ),
        Subscription(
            platform=PLATFORM_SIMPLEX,
            platform_chat_id="contact_mixed",
            from_asset="RBTC",
            to_asset="LN",
            fee_threshold=1.0,
        ),
    ]
    db_session.add_all(subscriptions)
    await db_session.commit()

    # Initial - no previous
    result = await check_fees(db_session, current_fees)
    assert len(result) == 0

    # Fee drops - both should be notified
    current_fees = {"RBTC": {"LN": 0.8}}
    result = await check_fees(db_session, current_fees)

    platforms = set(s.platform for s in result)
    assert PLATFORM_TELEGRAM in platforms or PLATFORM_SIMPLEX in platforms
