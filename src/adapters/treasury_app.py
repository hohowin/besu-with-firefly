"""Put the treasury app together and run it (adapter): client, gateway, service, API, server.

`python scripts/treasury_app.py` starts it. Needs the stack up and `stack.py treasury` run first.
"""

import json
import sys
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from src.adapters.firefly import FireflyClient, http_transport
from src.adapters.treasury_api import History, TreasuryApi
from src.adapters.treasury_http import UI_DIR, make_server
from src.adapters.trex_artifacts import REPO_ROOT
from src.core.treasury.errors import InvalidRate
from src.core.treasury.fx import Rates, parse_rates
from src.core.treasury.gateway import TreasuryGateway
from src.core.treasury.service import TreasuryService

NETWORK_DIR = REPO_ROOT / "network-config"
FX_FILE = NETWORK_DIR / "treasury" / "fx-rates.json"
LONDON = ZoneInfo("Europe/London")  # the requester's branch: LDN (TD-06)


class Sweepable(Protocol):
    def sweep(self) -> Any: ...


def load_fx_file(path: Path = FX_FILE) -> Rates:
    """Read the rate table. Called at every settlement, so a change needs no restart."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise InvalidRate(f"{path.name}: cannot be read ({error})") from error
    if not isinstance(document, dict):
        raise InvalidRate(f"{path.name}: must be a JSON object")
    try:
        return parse_rates(document)
    except InvalidRate as error:
        raise InvalidRate(f"{path.name}: {error}") from error


def load_wallet_addresses(network_dir: Path = NETWORK_DIR) -> dict[str, str]:
    """Wallet names and addresses. The private keys stay in wallets.json: FireFly signs."""
    document = json.loads((network_dir / "wallets.json").read_text(encoding="utf-8"))
    return {w["name"]: str(w["address"]).lower() for w in document["wallets"]}


class Sweeper:
    """Runs a sweep in the background, so an approve answers at once and steps 5 to 7 follow."""

    def __init__(self, service: Sweepable, log: Callable[[dict[str, Any]], None]) -> None:
        self._service = service
        self._log = log

    def trigger(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            self._service.sweep()
        except Exception as error:  # a sweep must never take the server down
            self._log({"action": "sweep", "outcome": "error", "message": str(error)})


def print_log(entry: dict[str, Any]) -> None:
    """One JSON line per step on stdout: requestId, action, operationId, outcome."""
    print(json.dumps(entry), flush=True)


def build_app(
    host: str = "127.0.0.1",
    port: int = 8080,
    allow_remote: bool = False,
    network_dir: Path = NETWORK_DIR,
    fx_file: Path = FX_FILE,
    log: Callable[[dict[str, Any]], None] = print_log,
) -> tuple[ThreadingHTTPServer, Sweeper]:
    wallets = load_wallet_addresses(network_dir)
    gateway = TreasuryGateway(FireflyClient(http_transport()), wallets)
    history = History()

    def record(entry: dict[str, Any]) -> None:
        log(entry)
        if "requestId" in entry:
            history.add(
                entry["requestId"],
                {**entry, "at": datetime.now(UTC).isoformat(), "message": entry["action"]},
            )

    service = TreasuryService(gateway, lambda: load_fx_file(fx_file), record)
    sweeper = Sweeper(service, log)
    api = TreasuryApi(
        gateway,
        wallets,
        lambda: load_fx_file(fx_file),
        lambda: service.notes,
        sweeper.trigger,
        history,
        lambda: datetime.now(UTC),
        LONDON,
    )
    return make_server(api, UI_DIR, host, port, allow_remote), sweeper


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Treasury branch-funding app (demo, no login)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--allow-remote", action="store_true", help="listen on a non-loopback host")
    parser.add_argument("--network-dir", type=Path, default=NETWORK_DIR)
    args = parser.parse_args(argv)
    try:
        server, sweeper = build_app(
            args.host,
            args.port,
            args.allow_remote,
            args.network_dir,
            args.network_dir / "treasury" / "fx-rates.json",
        )
    except (ValueError, OSError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"treasury app on http://{args.host}:{server.server_address[1]}/  (demo: no login)")
    sweeper.trigger()  # finish what an earlier run left approved or settled
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
