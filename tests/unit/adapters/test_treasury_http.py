import json
import threading
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from src.adapters.treasury_api import Response
from src.adapters.treasury_http import (
    MAX_BODY_BYTES,
    ensure_loopback,
    make_server,
    route_http,
)

HOSTS = frozenset({"127.0.0.1:8080", "localhost:8080"})
JSON = {"Host": "127.0.0.1:8080", "Content-Type": "application/json"}


class FakeApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Mapping[str, Any] | None]] = []

    def handle(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> Response:
        self.calls.append((method, path, body))
        return Response(202, {"status": "done"})


@pytest.fixture
def ui(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text("<h1>Treasury</h1>", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "app.css").write_text("body{}", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    return tmp_path


def call(
    api: FakeApi, ui: Path, method: str, path: str, headers: dict[str, str], body: bytes = b""
) -> tuple[int, dict[str, str], bytes]:
    return route_http(api, ui, HOSTS, method, path, headers, body)


# ---- the guards ----


@pytest.mark.parametrize(
    "host", ["evil.example", "127.0.0.1:9999", "localhost", "", "10.0.0.5:8080"]
)
def test_a_foreign_host_is_refused_against_dns_rebinding(ui: Path, host: str) -> None:
    api = FakeApi()
    status, _, _ = call(api, ui, "GET", "/api/requests", {"Host": host})
    assert status == 403
    assert api.calls == []


@pytest.mark.parametrize("host", ["127.0.0.1:8080", "localhost:8080"])
def test_the_local_host_names_are_accepted(ui: Path, host: str) -> None:
    status, _, _ = call(FakeApi(), ui, "GET", "/api/requests", {"Host": host})
    assert status == 202


@pytest.mark.parametrize("ctype", ["text/plain", "application/x-www-form-urlencoded", ""])
def test_a_post_that_is_not_json_is_refused_so_a_web_page_cannot_forge_one(
    ui: Path, ctype: str
) -> None:
    api = FakeApi()
    headers = {"Host": "127.0.0.1:8080", "Content-Type": ctype}
    status, _, _ = call(api, ui, "POST", "/api/requests/x/approve", headers, b'{"as":"tor"}')
    assert status == 415
    assert api.calls == []


def test_json_with_a_charset_is_fine(ui: Path) -> None:
    headers = {"Host": "127.0.0.1:8080", "Content-Type": "application/json; charset=utf-8"}
    api = FakeApi()
    assert call(api, ui, "POST", "/api/requests", headers, b'{"a": 1}')[0] == 202
    assert api.calls == [("POST", "/api/requests", {"a": 1})]


def test_a_big_body_is_refused(ui: Path) -> None:
    api = FakeApi()
    status, _, _ = call(api, ui, "POST", "/api/requests", JSON, b" " * (MAX_BODY_BYTES + 1))
    assert status == 413
    assert api.calls == []


@pytest.mark.parametrize("body", [b"{bad", b"[1]", b'"text"', b"\xff\xfe"])
def test_a_body_that_is_not_a_json_object_is_400(ui: Path, body: bytes) -> None:
    api = FakeApi()
    status, _, answer = call(api, ui, "POST", "/api/requests", JSON, body)
    assert status == 400
    assert json.loads(answer)["error"] == "invalid_json"
    assert api.calls == []


def test_an_empty_post_body_is_an_empty_object(ui: Path) -> None:
    api = FakeApi()
    call(api, ui, "POST", "/api/requests/x/retry-settle", JSON, b"")
    assert api.calls[0][2] == {}


# ---- answers ----


def test_api_answers_are_json_and_not_cached(ui: Path) -> None:
    status, headers, body = call(FakeApi(), ui, "GET", "/api/balances", {"Host": "127.0.0.1:8080"})
    assert status == 202
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert headers["Cache-Control"] == "no-store"
    assert json.loads(body) == {"status": "done"}


def test_the_page_and_its_two_files_are_served_with_a_strict_policy(ui: Path) -> None:
    host = {"Host": "127.0.0.1:8080"}
    for path, ctype in (
        ("/", "text/html"),
        ("/app.js", "text/javascript"),
        ("/app.css", "text/css"),
    ):
        status, headers, body = call(FakeApi(), ui, "GET", path, host)
        assert status == 200 and body
        assert headers["Content-Type"].startswith(ctype)
        assert "default-src 'self'" in headers["Content-Security-Policy"]
        assert "'unsafe-inline'" not in headers["Content-Security-Policy"]
        assert headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize(
    "path", ["/secret.txt", "/../secret.txt", "/%2e%2e/secret.txt", "/static/app.js"]
)
def test_only_the_three_ui_files_are_served(ui: Path, path: str) -> None:
    status, _, _ = call(FakeApi(), ui, "GET", path, {"Host": "127.0.0.1:8080"})
    assert status == 404


def test_a_missing_ui_file_is_404_not_a_crash(tmp_path: Path) -> None:
    status, _, _ = call(FakeApi(), tmp_path, "GET", "/", {"Host": "127.0.0.1:8080"})
    assert status == 404


# ---- binding ----


def test_only_a_loopback_address_is_allowed_by_default() -> None:
    ensure_loopback("127.0.0.1", allow_remote=False)
    ensure_loopback("localhost", allow_remote=False)
    for host in ("0.0.0.0", "192.168.1.5", ""):
        with pytest.raises(ValueError, match="allow-remote"):
            ensure_loopback(host, allow_remote=False)
    ensure_loopback("0.0.0.0", allow_remote=True)


def test_a_real_server_answers_on_loopback_and_refuses_a_forged_post(ui: Path) -> None:
    api = FakeApi()
    server = make_server(api, ui, "127.0.0.1", 0, allow_remote=False)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/balances", timeout=5) as ok:
            assert ok.status == 202
        forged = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/requests",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "text/plain"},
        )
        with pytest.raises(urllib.error.HTTPError) as refused:
            urllib.request.urlopen(forged, timeout=5)
        assert refused.value.code == 415
        refused.value.close()
    finally:
        server.shutdown()
        server.server_close()
    assert [c[:2] for c in api.calls] == [("GET", "/api/balances")]
