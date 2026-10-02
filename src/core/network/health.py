"""Interpret `docker compose ps --format json` output (pure parsing, no I/O)."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContainerState:
    service: str
    state: str  # running, exited, ...
    health: str  # healthy, starting, unhealthy, or "" when the image has no healthcheck


def parse_compose_ps(output: str) -> list[ContainerState]:
    """Parse one JSON object per line (Compose v2) or a single JSON array."""
    text = output.strip()
    if not text:
        return []
    try:
        if text.startswith("["):
            items: list[dict[str, Any]] = json.loads(text)
        else:
            items = [json.loads(line) for line in text.splitlines() if line.strip()]
    except json.JSONDecodeError as error:
        raise ValueError(f"could not parse docker compose ps output: {error}") from error
    return [
        ContainerState(
            service=str(item.get("Service") or item.get("Name", "")),
            state=str(item.get("State", "")),
            health=str(item.get("Health", "")),
        )
        for item in items
    ]


def all_healthy(states: Sequence[ContainerState], expected_services: Sequence[str]) -> bool:
    """True when every expected service is running and healthy."""
    by_service = {s.service: s for s in states}
    return all(
        name in by_service
        and by_service[name].state == "running"
        and by_service[name].health == "healthy"
        for name in expected_services
    )
