"""The treasury web server (adapter): the JSON API and the three files of the page, on loopback.

Standard library only. Handlers are synchronous (a write waits for FireFly), one thread per
request. Two guards matter because anything on the machine can reach 127.0.0.1, including a web
page in the user's own browser:
- the `Host` header must be the local name and port, which stops DNS rebinding;
- a POST must be `application/json`, which a web page on another origin cannot send without a
  CORS preflight that this server never answers.
"""

import json
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from src.adapters.treasury_api import Response

MAX_BODY_BYTES = 16 * 1024
UI_DIR = Path(__file__).resolve().parent / "treasury_ui"

_PAGE_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
}
_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'none'"
    ),
}
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}

HttpAnswer = tuple[int, dict[str, str], bytes]


class Api(Protocol):
    def handle(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> Response: ...


def ensure_loopback(host: str, allow_remote: bool) -> None:
    if host not in _LOOPBACK and not allow_remote:
        raise ValueError(
            f"{host!r} is not a loopback address. The treasury app has no login, so it listens "
            "on 127.0.0.1 only; pass --allow-remote to override."
        )


def route_http(
    api: Api,
    ui_dir: Path,
    allowed_hosts: frozenset[str],
    method: str,
    target: str,
    headers: Mapping[str, str],
    body: bytes,
) -> HttpAnswer:
    """One request to one answer. No sockets, so every rule is tested directly."""
    lowered = {name.lower(): value for name, value in headers.items()}
    if lowered.get("host", "") not in allowed_hosts:
        return _json(403, {"status": "error", "error": "bad_host", "message": "wrong Host header"})
    path = urlsplit(target).path
    if method == "GET" and path in _PAGE_FILES:
        return _page(ui_dir, path)
    if not path.startswith("/api/"):
        return _json(404, _problem("not_found", f"no route for {method} {path}"))
    if method == "POST":
        content_type = lowered.get("content-type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            return _json(415, _problem("unsupported_media_type", "send application/json"))
        if len(body) > MAX_BODY_BYTES:
            return _json(413, _problem("too_large", f"at most {MAX_BODY_BYTES} bytes"))
        parsed = _parse(body)
        if parsed is None:
            return _json(400, _problem("invalid_json", "the body must be a JSON object"))
        response = api.handle(method, path, parsed)
    else:
        response = api.handle(method, path)
    return _json(response.status, response.body)


def _parse(body: bytes) -> dict[str, Any] | None:
    if not body.strip():
        return {}
    try:
        value = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _page(ui_dir: Path, path: str) -> HttpAnswer:
    name, content_type = _PAGE_FILES[path]
    file = ui_dir / name
    if not file.is_file():
        return _json(404, _problem("not_found", f"{name} is missing"))
    return 200, {**_SECURITY_HEADERS, "Content-Type": content_type}, file.read_bytes()


def _json(status: int, body: Mapping[str, Any]) -> HttpAnswer:
    headers = {**_SECURITY_HEADERS, "Content-Type": "application/json; charset=utf-8"}
    return status, headers, json.dumps(body).encode("utf-8")


def _problem(code: str, message: str) -> dict[str, str]:
    return {"status": "error", "error": code, "message": message}


def make_server(
    api: Api, ui_dir: Path, host: str, port: int, allow_remote: bool = False
) -> ThreadingHTTPServer:
    """A server bound to `host:port` (port 0 picks a free one). Call `serve_forever` on it."""
    ensure_loopback(host, allow_remote)
    holder: dict[str, frozenset[str]] = {}

    class Handler(BaseHTTPRequestHandler):
        def _serve(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(min(length, MAX_BODY_BYTES + 1)) if length else b""
            status, headers, answer = route_http(
                api, ui_dir, holder["hosts"], self.command, self.path, dict(self.headers), body
            )
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(answer)))
            self.end_headers()
            self.wfile.write(answer)

        do_GET = _serve
        do_POST = _serve
        do_PUT = _serve
        do_DELETE = _serve

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass  # request lines carry ids only, but the service logs what matters

    server = ThreadingHTTPServer((host, port), Handler)
    bound = server.server_address[1]
    holder["hosts"] = frozenset({f"127.0.0.1:{bound}", f"localhost:{bound}"})
    return server
