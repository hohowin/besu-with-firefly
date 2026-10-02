"""Bounded polling for integration tests: wait for a condition, fail with a useful message."""

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def wait_for(
    probe: Callable[[], T | None],
    *,
    describe: str,
    timeout: float = 60.0,
    interval: float = 2.0,
) -> T:
    """Call `probe` until it returns something other than None or False, or fail after `timeout`.

    `describe` names what we were waiting for, so a failure says what was observed last.
    """
    deadline = time.monotonic() + timeout
    last: object = None
    while True:
        try:
            last = probe()
        except Exception as error:  # a probe may fail while the stack is still starting
            last = f"{type(error).__name__}: {error}"
        else:
            if last is not None and last is not False:
                return last
        if time.monotonic() >= deadline:
            raise AssertionError(
                f"timed out after {timeout:g}s waiting for {describe}; last: {last!r}"
            )
        time.sleep(interval)
