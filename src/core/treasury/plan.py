"""The treasury deployment plan (pure data): two currency tokens and the request contract.

Runs through the same `run_plan` as the T-REX plan. The wallets are the three treasury wallets
plus `admin`, who deploys and sets each token's controller.
"""

from src.core.treasury.money import MAX_AMOUNT_MINOR
from src.core.trex.plan import KNOWN_ACCOUNTS, Account, Artifact, Call, Deploy, Ref, Step

PACKAGE = "treasury"  # `contracts/treasury/compiled/`
TOKEN_ARTIFACT = Artifact(PACKAGE, "CurrencyToken.json")
REQUEST_ARTIFACT = Artifact(PACKAGE, "FundingRequest.json")

# The wallet that holds each role on `FundingRequest`.
ROLE_ACCOUNTS = {"requester": "ldn", "approver": "tor", "treasury": "treasury"}
NEW_WALLETS = ("ldn", "tor", "treasury")
TREASURY_ACCOUNTS = KNOWN_ACCOUNTS | frozenset(NEW_WALLETS)

# Bounds the contract enforces on the rate passed to `settle`, in parts per million. Tight on
# purpose: a real CAD to GBP rate is about 0.55 to 0.60, so a typo is refused, not paid.
MIN_RATE_PPM = 400_000  # 0.400000
MAX_RATE_PPM = 800_000  # 0.800000

# FireFly API name, the deployed contract it points at, and the artifact that describes it.
APIS = [
    ("cadc", "cadc", TOKEN_ARTIFACT),
    ("gbpc", "gbpc", TOKEN_ARTIFACT),
    ("funding-request", "funding-request", REQUEST_ARTIFACT),
]


def build_plan() -> list[Step]:
    return [
        Deploy("cadc", TOKEN_ARTIFACT, ("Canadian Dollar Coin", "CADC", Account("admin"))),
        Deploy("gbpc", TOKEN_ARTIFACT, ("Pound Sterling Coin", "GBPC", Account("admin"))),
        Deploy(
            "funding-request",
            REQUEST_ARTIFACT,
            (
                Ref("cadc"),
                Ref("gbpc"),
                Account(ROLE_ACCOUNTS["treasury"]),
                (Account(ROLE_ACCOUNTS["requester"]),),
                (Account(ROLE_ACCOUNTS["approver"]),),
                MAX_AMOUNT_MINOR,
                MIN_RATE_PPM,
                MAX_RATE_PPM,
            ),
        ),
        Call("cadc", "setController", (Ref("funding-request"),)),
        Call("gbpc", "setController", (Ref("funding-request"),)),
    ]
