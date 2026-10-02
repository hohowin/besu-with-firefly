import pytest

from src.core.firefly.operations import (
    already_submitted_transaction,
    deploy_body,
    invoke_body,
    parse_operation,
    query_body,
)

ABI = [{"type": "constructor", "inputs": []}]
METHOD = {"name": "set", "params": [{"name": "v", "schema": {"type": "integer"}}], "returns": []}
ADDRESS = "0x" + "ab" * 20


def test_deploy_body_carries_bytecode_abi_constructor_input_and_key() -> None:
    body = deploy_body("0x6080", ABI, ["Coin"], key="0xkey", idempotency_key="deploy-token")
    assert body == {
        "contract": "0x6080",
        "definition": ABI,
        "input": ["Coin"],
        "key": "0xkey",
        "idempotencyKey": "deploy-token",
    }


def test_deploy_body_leaves_out_what_was_not_given() -> None:
    assert deploy_body("0x6080", ABI, []) == {"contract": "0x6080", "definition": ABI, "input": []}


def test_invoke_body_names_the_location_the_method_and_the_signer() -> None:
    body = invoke_body(ADDRESS, METHOD, {"v": 7}, key="0xkey", idempotency_key="k1")
    assert body == {
        "location": {"address": ADDRESS},
        "method": METHOD,
        "input": {"v": 7},
        "key": "0xkey",
        "idempotencyKey": "k1",
    }


def test_query_body_has_no_key_and_no_idempotency_key() -> None:
    assert query_body(ADDRESS, METHOD, {"v": 1}) == {
        "location": {"address": ADDRESS},
        "method": METHOD,
        "input": {"v": 1},
    }


def test_parse_operation_reads_status_id_tx_and_output() -> None:
    op = parse_operation(
        {
            "id": "op1",
            "status": "Succeeded",
            "tx": "tx1",
            "type": "blockchain_deploy",
            "output": {"contractLocation": {"address": ADDRESS}},
        }
    )
    assert (op.id, op.status, op.tx) == ("op1", "Succeeded", "tx1")
    assert op.succeeded and not op.failed
    assert op.output["contractLocation"]["address"] == ADDRESS


def test_parse_operation_marks_failed_operations_with_their_error_text() -> None:
    op = parse_operation({"id": "op2", "status": "Failed", "error": "execution reverted: nope"})
    assert op.failed and not op.succeeded
    assert op.error == "execution reverted: nope"


def test_a_pending_operation_is_neither_succeeded_nor_failed() -> None:
    op = parse_operation({"id": "op3", "status": "Pending"})
    assert not op.succeeded and not op.failed


def test_parse_operation_rejects_a_body_that_is_not_an_operation() -> None:
    with pytest.raises(ValueError, match="not a FireFly operation"):
        parse_operation({"error": "FF10111: nope"})


def test_a_409_ff10431_is_an_already_submitted_write_with_the_original_transaction() -> None:
    body = {"error": "FF10431: Idempotency key 'k1' already used for transaction 'tx-original'"}
    assert already_submitted_transaction(409, body) == "tx-original"


def test_other_responses_are_not_already_submitted() -> None:
    assert already_submitted_transaction(409, {"error": "FF99999: something else"}) is None
    not_a_conflict = {"error": "FF10431: used for transaction 'tx'"}
    assert already_submitted_transaction(200, not_a_conflict) is None
    assert already_submitted_transaction(500, "boom") is None


def test_api_bodies_pass_inputs_by_name_and_only_writes_carry_a_signer() -> None:
    from src.core.firefly.operations import api_invoke_body, api_query_body

    assert api_query_body({"_userAddress": ADDRESS}) == {"input": {"_userAddress": ADDRESS}}
    assert api_invoke_body({"_amount": 5}, key="0xk", idempotency_key="i1") == {
        "input": {"_amount": 5},
        "key": "0xk",
        "idempotencyKey": "i1",
    }
    assert api_invoke_body({}, key="0xk") == {"input": {}, "key": "0xk"}
