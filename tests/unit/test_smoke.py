"""Smoke test: the layers named in PROJECT.md exist and are importable."""

import importlib

import pytest


@pytest.mark.parametrize("module", ["src.core", "src.adapters"])
def test_layer_is_importable(module: str) -> None:
    assert importlib.import_module(module) is not None


def test_core_does_not_import_io_modules() -> None:
    """src/core is pure logic: no process, network or terminal access (PROJECT.md Layers)."""
    import pkgutil

    import src.core as core

    forbidden = {"subprocess", "socket", "urllib", "http", "requests", "httpx"}
    for info in pkgutil.walk_packages(core.__path__, prefix="src.core."):
        source = importlib.import_module(info.name).__dict__
        imported = {
            getattr(value, "__name__", "").split(".")[0]
            for value in source.values()
            if hasattr(value, "__name__")
        }
        assert not (forbidden & imported), f"{info.name} imports an I/O module"
