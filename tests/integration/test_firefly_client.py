"""The FireFly client adapter against the real FireFly (no contract needed)."""

import pytest

from src.adapters.docker_stack import DockerStack
from src.adapters.firefly import FireflyClient, FireflyError, http_transport

pytestmark = pytest.mark.integration


def test_status_through_the_real_transport(stack: DockerStack) -> None:
    status = FireflyClient(http_transport()).status()
    assert status["namespace"]["name"] == "default"
    assert status["multiparty"]["enabled"] is False


def test_an_unknown_operation_is_a_firefly_error_with_fireflys_own_message(
    stack: DockerStack,
) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(FireflyError, match=r"HTTP 404.*FF00164"):
        FireflyClient(http_transport()).get_operation(unknown)


def test_querying_a_contract_that_does_not_exist_is_a_firefly_error(stack: DockerStack) -> None:
    method = {"name": "get", "params": [], "returns": []}
    with pytest.raises(FireflyError, match="HTTP"):
        FireflyClient(http_transport()).query("0x" + "00" * 20, method, {})


def test_an_unreachable_firefly_is_a_firefly_error_that_names_the_request() -> None:
    client = FireflyClient(http_transport("http://127.0.0.1:1", timeout=2))
    with pytest.raises(FireflyError, match=r"GET /api/v1/status could not reach FireFly"):
        client.status()
