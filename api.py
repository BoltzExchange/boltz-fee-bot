from httpx import AsyncClient

from consts import SwapType, Fees
from utils import currency_to_asset


async def get_all_fees(client: AsyncClient) -> Fees:
    result = {}
    for swap_type in SwapType:
        fees = await get_fees(client, swap_type)
        for from_asset, pairs in fees.items():
            result.setdefault(from_asset, {}).update(pairs)
    return result


async def get_fees(client: AsyncClient, swap_type: SwapType) -> Fees:
    response = await client.get(
        f"/v2/swap/{swap_type.value}", headers={"Referral": "pro"}
    )
    response.raise_for_status()
    data = response.json()

    fees = {}
    for quote_currency in data:
        from_asset = currency_to_asset(swap_type, quote_currency, True)
        fees[from_asset] = {}
        for base_currency in data[quote_currency]:
            to_asset = currency_to_asset(swap_type, base_currency, False)
            fees[from_asset][to_asset] = data[quote_currency][base_currency]["fees"][
                "percentage"
            ]

    return fees
