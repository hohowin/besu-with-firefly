"""Request ids and idempotency keys (pure).

The form makes a UUID when it loads, so a double click or a retried POST carries the same id.
On the chain the id is the UUID's 16 bytes left-padded to 32 (`bytes32`), which stays readable.
"""

import uuid

from src.core.treasury.request import Action

_PAD = "00" * 16


def request_id_from_uuid(text: str) -> str:
    """UUID text to the `0x...` bytes32 the contract takes. Raises `ValueError` if not a UUID."""
    return "0x" + _PAD + uuid.UUID(text.strip()).hex


def uuid_from_request_id(request_id: str) -> str:
    """The reverse. Raises `ValueError` for an id this app did not make."""
    digits = request_id.removeprefix("0x")
    if len(digits) != 64 or not digits.startswith(_PAD):
        raise ValueError(f"{request_id!r} is not a request id made by this app")
    return str(uuid.UUID(digits[32:]))


def idempotency_key(request_uuid: str, action: Action) -> str:
    """One key per request and action: sending the same step twice is the same write."""
    return f"{request_uuid}:{action.value}"
