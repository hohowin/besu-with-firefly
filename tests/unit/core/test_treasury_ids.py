import pytest

from src.core.treasury.ids import idempotency_key, request_id_from_uuid, uuid_from_request_id
from src.core.treasury.request import Action

UUID = "123e4567-e89b-12d3-a456-426614174000"


def test_request_id_is_32_bytes_and_reversible() -> None:
    request_id = request_id_from_uuid(UUID)
    assert request_id == "0x" + "00" * 16 + "123e4567e89b12d3a456426614174000"
    assert uuid_from_request_id(request_id) == UUID


def test_request_id_accepts_any_uuid_spelling() -> None:
    assert request_id_from_uuid(UUID.upper()) == request_id_from_uuid(UUID)


@pytest.mark.parametrize("bad", ["", "abc", "123e4567-e89b-12d3-a456-42661417400", "0x" + "0" * 64])
def test_request_id_rejects_non_uuid(bad: str) -> None:
    with pytest.raises(ValueError):
        request_id_from_uuid(bad)


def test_uuid_from_request_id_rejects_ids_that_are_not_ours() -> None:
    with pytest.raises(ValueError):
        uuid_from_request_id("0x" + "11" * 32)


def test_idempotency_key_differs_per_action() -> None:
    keys = {idempotency_key(UUID, action) for action in Action}
    assert len(keys) == len(Action)
    assert idempotency_key(UUID, Action.SETTLE) == f"{UUID}:settle"
