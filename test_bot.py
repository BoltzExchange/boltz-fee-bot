import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot import check_subscription, check_fees
from db import Subscription


@pytest.mark.parametrize(
    "current_fees, previous_fees, from_asset, to_asset, threshold, expected, test_description",
    [
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
    ],
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
    subscription = Subscription(
        chat_id=123, from_asset=from_asset, to_asset=to_asset, fee_threshold=threshold
    )

    result = check_subscription(current_fees, previous_fees, subscription)
    assert result == expected, f"Failed case: {test_description}"


@pytest.mark.asyncio(loop_scope="session")
async def test_check_fees(db_session: AsyncSession):
    current_fees = {"BTC": {"LN": 1.2}}
    subscriptions = [
        Subscription(chat_id=123, from_asset="BTC", to_asset="LN", fee_threshold=1.0),
        Subscription(chat_id=123, from_asset="BTC", to_asset="LN", fee_threshold=0.5),
    ]
    db_session.add_all(subscriptions)
    await db_session.commit()
    result = await check_fees(db_session, current_fees)
    assert len(result) == 0

    current_fees = {"BTC": {"LN": 0.8}}
    result = await check_fees(db_session, current_fees)
    assert result[0].id == subscriptions[0].id, "Failed to check fees"
