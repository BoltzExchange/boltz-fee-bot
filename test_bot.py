import pytest
from bot import check_subscriber
from db import Subscriber


@pytest.mark.parametrize(
    "current_fees, previous_fees, from_asset, to_asset, threshold, expected, test_description",
    [
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
def test_check_subscriber(
    current_fees,
    previous_fees,
    from_asset,
    to_asset,
    threshold,
    expected,
    test_description,
):
    subscriber = Subscriber(
        chat_id=123, from_asset=from_asset, to_asset=to_asset, fee_threshold=threshold
    )

    result = check_subscriber(current_fees, previous_fees, subscriber)
    assert result == expected, f"Failed case: {test_description}"
