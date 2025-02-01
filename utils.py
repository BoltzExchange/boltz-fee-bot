from urllib.parse import urlencode

from consts import PRO_URL, SwapType


def currency_to_asset(swap_type: SwapType, currency: str, is_send: bool):
    match swap_type:
        case SwapType.SUBMARINE:
            return "LN" if not is_send and currency == "BTC" else currency
        case SwapType.REVERSE:
            return "LN" if is_send and currency == "BTC" else currency
        case _:
            return currency


def encode_url_params(from_asset: str, to_asset: str) -> str:
    params = {"sendAsset": from_asset, "receiveAsset": to_asset}

    return f"{PRO_URL}?{urlencode(params)}"
