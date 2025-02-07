import enum

Fees = dict[str, dict[str, float]]

PRO_URL = "https://pro.boltz.exchange"

SUBMARINE_SWAP_TYPE = "submarine"

ALL_FEES = "all_fees"


class SwapType(enum.Enum):
    SUBMARINE = "submarine"
    REVERSE = "reverse"
    CHAIN = "chain"
