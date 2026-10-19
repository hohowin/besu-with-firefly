"""Static rules for the page (TR-NFR-03, design §11): nothing the strict policy would block, and
nothing that could run text from the server as code."""

import re
from pathlib import Path

import pytest

from src.adapters.treasury_http import UI_DIR

FILES = ["index.html", "app.js", "app.css"]


def text(name: str) -> str:
    return (UI_DIR / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", FILES)
def test_the_file_exists(name: str) -> None:
    assert (UI_DIR / name).is_file()


def test_the_page_has_no_inline_script_style_or_handler() -> None:
    page = text("index.html")
    scripts = re.findall(r"<script\b[^>]*>", page)
    assert scripts == ['<script src="/app.js">']
    assert "<style" not in page
    assert not re.search(r"\sstyle\s*=", page)
    assert not re.search(r"\son[a-z]+\s*=", page)


def test_the_script_never_puts_server_text_in_as_html() -> None:
    script = text("app.js")
    for banned in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.write",
        "eval(",
        "new Function",
    ):
        assert banned not in script, banned


@pytest.mark.parametrize("name", FILES)
def test_nothing_is_loaded_from_another_site(name: str) -> None:
    assert not re.search(r"https?://", text(name))


def test_the_script_uses_the_routes_the_api_has() -> None:
    script = text("app.js")
    for route in (
        "/api/requests",
        "/api/balances",
        "/api/fx",
        "/approve",
        "/reject",
        "/retry-settle",
    ):
        assert route in script


def test_every_element_the_script_looks_up_exists_in_the_page() -> None:
    page = text("index.html")
    ids = set(re.findall(r'getElementById\("([a-z-]+)"\)', text("app.js")))
    ids.update(f"tab-{t}" for t in ("ldn", "tor", "ledger"))
    ids.update(f"view-{t}" for t in ("ldn", "tor", "ledger"))
    ids.discard("tab-")
    ids.discard("view-")
    missing = {i for i in ids if f'id="{i}"' not in page and i not in ("tab-", "view-")}
    assert missing == set()


def test_ui_dir_is_inside_the_adapters_package() -> None:
    assert Path(__file__).resolve().parents[3] / "src" / "adapters" / "treasury_ui" == UI_DIR
