import pytest
from url_params import encode_url_params
from consts import PRO_URL, SUBMARINE_SWAP_TYPE


@pytest.mark.parametrize(
    "swap_type,from_currency,to_currency,expected_receive_asset",
    [
        (SUBMARINE_SWAP_TYPE, "BTC", "BTC", "LN"),
        (SUBMARINE_SWAP_TYPE, "L-BTC", "BTC", "LN"),
        (SUBMARINE_SWAP_TYPE, "RBTC", "BTC", "LN"),
        ("reverse", "BTC", "BTC", "BTC"),
    ],
)
def test_encode_url_params(
    swap_type, from_currency, to_currency, expected_receive_asset
):
    result = encode_url_params(swap_type, from_currency, to_currency)
    assert (
        result
        == f"{PRO_URL}?sendAsset={from_currency}&receiveAsset={expected_receive_asset}"
    )
