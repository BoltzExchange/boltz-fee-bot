from urllib.parse import urlencode

from consts import PRO_URL, SUBMARINE_SWAP_TYPE


def encode_url_params(swap_type: str, from_currency: str, to_currency: str) -> str:
    params = {
        "sendAsset": from_currency,
        "receiveAsset": "LN"
        if swap_type == SUBMARINE_SWAP_TYPE and to_currency == "BTC"
        else to_currency,
    }

    return f"{PRO_URL}?{urlencode(params)}"
