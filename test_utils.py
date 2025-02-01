import pytest
from utils import currency_to_asset
from consts import SwapType


@pytest.mark.parametrize(
    "swap_type, currency, is_send, expected",
    [
        (SwapType.SUBMARINE, "BTC", False, "LN"),
        (SwapType.SUBMARINE, "BTC", True, "BTC"),
        (SwapType.SUBMARINE, "L-BTC", False, "L-BTC"),
        (SwapType.SUBMARINE, "RBTC", False, "RBTC"),
        (SwapType.REVERSE, "BTC", True, "LN"),
        (SwapType.REVERSE, "BTC", False, "BTC"),
        (SwapType.REVERSE, "L-BTC", True, "L-BTC"),
        (SwapType.REVERSE, "RBTC", True, "RBTC"),
    ],
)
def test_currency_to_asset(swap_type, currency, is_send, expected):
    assert currency_to_asset(swap_type, currency, is_send) == expected
