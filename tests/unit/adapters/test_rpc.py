import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.adapters.rpc import chain_heights_reader


class Handler(BaseHTTPRequestHandler):
    height = "0x5"

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        request = json.loads(self.rfile.read(length))
        assert request["method"] == "eth_blockNumber"
        body = json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": type(self).height})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, format: str, *args: object) -> None:  # silence the test server
        pass


@pytest.fixture
def server() -> Iterator[str]:
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_reader_returns_the_height_of_each_node(server: str) -> None:
    Handler.height = "0x1f"
    read = chain_heights_reader({"anson": server, "beatrice": server})
    assert read() == {"anson": 31, "beatrice": 31}


def test_reader_reports_an_unreachable_node_as_none(server: str) -> None:
    read = chain_heights_reader({"up": server, "down": "http://127.0.0.1:1"})
    heights = read()
    assert heights["down"] is None
    assert heights["up"] is not None


def test_wait_for_chain_returns_at_once_when_every_node_has_blocks() -> None:
    from src.adapters.rpc import wait_for_chain

    slept: list[float] = []
    wait_for_chain(lambda: {"rpc": 7}, sleep=slept.append)
    assert slept == []


def test_wait_for_chain_waits_while_a_node_is_at_block_zero_or_unreachable() -> None:
    from src.adapters.rpc import wait_for_chain

    answers: Iterator[dict[str, int | None]] = iter([{"rpc": None}, {"rpc": 0}, {"rpc": 3}])
    slept: list[float] = []
    ticks = iter(range(1000))
    wait_for_chain(
        lambda: next(answers), sleep=slept.append, clock=lambda: float(next(ticks)), poll=2.0
    )
    assert slept == [2.0, 2.0]


def test_wait_for_chain_gives_up_and_names_the_node_that_is_not_moving() -> None:
    from src.adapters.docker_stack import StackError
    from src.adapters.rpc import wait_for_chain

    ticks = iter(range(1000))
    with pytest.raises(StackError, match=r"rpc is still at block 0"):
        wait_for_chain(
            lambda: {"rpc": 0},
            timeout=5.0,
            sleep=lambda _s: None,
            clock=lambda: float(next(ticks)),
        )
    with pytest.raises(StackError, match=r"rpc is unreachable"):
        wait_for_chain(
            lambda: {"rpc": None},
            timeout=5.0,
            sleep=lambda _s: None,
            clock=lambda: float(next(ticks)),
        )
