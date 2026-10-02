"""Ethereum contract size limits (pure)."""

MAX_DEPLOYED_BYTES = 24_576  # EIP-170: runtime code of a contract
MAX_INIT_BYTES = 49_152  # EIP-3860 (Shanghai): init code of a creation transaction


def size_problems(name: str, deployed_bytes: int, init_bytes: int) -> list[str]:
    """Why a contract would not deploy on a Shanghai chain. Empty when both sizes fit."""
    problems = []
    if deployed_bytes > MAX_DEPLOYED_BYTES:
        problems.append(
            f"{name}: deployed code is {deployed_bytes} bytes, over the {MAX_DEPLOYED_BYTES} limit"
        )
    if init_bytes > MAX_INIT_BYTES:
        problems.append(f"{name}: init code is {init_bytes} bytes, over the {MAX_INIT_BYTES} limit")
    return problems
