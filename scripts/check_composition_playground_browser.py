#!/usr/bin/env python3
"""Run real-browser acceptance checks for the Site Composition Playground."""

from __future__ import annotations

import argparse
import gzip
import shutil
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "docs" / "composition-playground.md"
FIXTURE = ROOT / "tests" / "fixtures" / "composition-playground-v1-explain.json"
CORE_JS = ROOT / "assets" / "javascripts" / "composition-playground.js"
EXPLAIN_JS = ROOT / "assets" / "javascripts" / "composition-playground-explain.js"
CSS = ROOT / "assets" / "stylesheets" / "composition-playground.css"


class PlaygroundBrowserError(RuntimeError):
    pass


def playground_markup() -> str:
    text = DOCUMENT.read_text(encoding="utf-8")
    start = text.find('<div id="composition-playground"')
    end = text.find("\n\n## v1 scope", start)
    if start < 0 or end < 0:
        raise PlaygroundBrowserError("Playground reader markup could not be extracted")
    markup = text[start:end].strip()
    for marker in (
        "data-playground-app",
        "data-playground-explain",
        "data-playground-groups",
        "data-playground-contracts",
        "data-playground-material-tree",
    ):
        if marker not in markup:
            raise PlaygroundBrowserError(f"Playground reader markup is missing {marker}")
    return markup


def prepare_harness(root: Path) -> None:
    (root / "javascripts").mkdir(parents=True)
    (root / "stylesheets").mkdir(parents=True)
    (root / "composition" / "playground").mkdir(parents=True)
    shutil.copyfile(CORE_JS, root / "javascripts" / CORE_JS.name)
    shutil.copyfile(EXPLAIN_JS, root / "javascripts" / EXPLAIN_JS.name)
    shutil.copyfile(CSS, root / "stylesheets" / CSS.name)
    raw_fixture = FIXTURE.read_bytes()
    (root / "composition" / "playground" / "composition-playground-v1.json.gz").write_bytes(
        gzip.compress(raw_fixture, compresslevel=9, mtime=0)
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Composition Playground acceptance</title>
  <style>html {{ box-sizing: border-box; }} *, *::before, *::after {{ box-sizing: inherit; }} body {{ margin: 0; padding: 1rem; font: 16px/1.5 sans-serif; }} main {{ max-width: 72rem; margin-inline: auto; }}</style>
  <link rel="stylesheet" href="/stylesheets/composition-playground.css">
  <script src="/javascripts/composition-playground.js" defer></script>
  <script src="/javascripts/composition-playground-explain.js" defer></script>
</head>
<body><main>{playground_markup()}</main></body>
</html>
"""
    (root / "index.html").write_text(html, encoding="utf-8")


def serve(root: Path) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, f"http://{host}:{port}/"


def assert_mobile_layout(page: Any) -> None:
    metrics = page.evaluate(
        """() => ({
          innerWidth: window.innerWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          appHidden: document.querySelector('[data-playground-app]').hidden,
          explainHidden: document.querySelector('[data-playground-explain]').hidden
        })"""
    )
    if metrics["innerWidth"] != 360 or metrics["clientWidth"] != 360:
        raise PlaygroundBrowserError(f"unexpected mobile viewport metrics: {metrics}")
    if metrics["scrollWidth"] > metrics["clientWidth"] + 1:
        raise PlaygroundBrowserError(f"Playground has horizontal overflow at 360px: {metrics}")
    if metrics["appHidden"] or metrics["explainHidden"]:
        raise PlaygroundBrowserError(f"Playground did not become visible: {metrics}")


def run_browser_check() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaygroundBrowserError(
            "Playwright is required; install requirements-visual.txt"
        ) from exc

    with tempfile.TemporaryDirectory(prefix="composition-playground-browser-") as directory:
        harness = Path(directory)
        prepare_harness(harness)
        server, thread, base_url = serve(harness)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 360, "height": 800})
                page_errors: list[str] = []
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.goto(base_url, wait_until="networkidle")
                page.wait_for_selector("[data-playground-app]:not([hidden])")
                page.wait_for_selector("[data-playground-explain]:not([hidden])")
                assert_mobile_layout(page)

                recipe = page.locator("[data-playground-recipe]")
                recipe.focus()
                page.keyboard.press("Tab")
                active = page.evaluate(
                    """() => ({tag: document.activeElement?.tagName, type: document.activeElement?.type, value: document.activeElement?.value})"""
                )
                if active != {"tag": "INPUT", "type": "checkbox", "value": "capability.cli"}:
                    raise PlaygroundBrowserError(f"keyboard order did not reach first optional component: {active}")
                page.keyboard.press("Space")
                page.wait_for_function("() => location.hash.includes('include=capability.cli')")
                page.wait_for_function(
                    "() => Array.from(document.querySelectorAll('[data-playground-resolved] li')).some((node) => node.textContent === 'foundation.web')"
                )

                explanation = page.locator("[data-playground-explain]").text_content() or ""
                for expected in (
                    "foundation.web",
                    "Required directly by capability.cli.",
                    "cli-interface",
                    "web/routes.json",
                    "ownership: generated",
                    "Canonical empty-target initial plan: 3 create.",
                ):
                    if expected not in explanation:
                        raise PlaygroundBrowserError(f"explainability output is missing {expected!r}")

                details = page.locator("[data-playground-explain] details").first
                summary = details.locator("summary")
                summary.focus()
                if not details.evaluate("node => node.open"):
                    raise PlaygroundBrowserError("first explainability disclosure should start open")
                page.keyboard.press("Enter")
                if details.evaluate("node => node.open"):
                    raise PlaygroundBrowserError("Enter did not close native details disclosure")
                page.keyboard.press("Enter")
                if not details.evaluate("node => node.open"):
                    raise PlaygroundBrowserError("Enter did not reopen native details disclosure")

                assert_mobile_layout(page)
                page.reload(wait_until="networkidle")
                page.wait_for_selector("[data-playground-explain]:not([hidden])")
                if not page.locator('input[type="checkbox"][value="capability.cli"]').is_checked():
                    raise PlaygroundBrowserError("shareable URL hash did not restore the selected component")
                assert_mobile_layout(page)
                if page_errors:
                    raise PlaygroundBrowserError(f"browser page errors: {page_errors}")
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description=__doc__).parse_args()


def main() -> int:
    parse_args()
    try:
        run_browser_check()
    except (OSError, PlaygroundBrowserError) as exc:
        raise SystemExit(str(exc)) from exc
    print("Composition Playground browser acceptance passed at 360px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
