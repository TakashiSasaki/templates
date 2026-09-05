#!/usr/bin/env python3
"""Focused Chromium regressions for final Composition Playground Site remediation."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from check_composition_playground_browser import (
    PlaygroundBrowserError,
    playground_markup,
    prepare_harness,
    serve as serve_harness,
)
from check_composition_playground_cross_authority import serve as serve_built_site


def add_heading_anchor(root: Path) -> None:
    for relative in ("index.html", "playground/index.html", "home/index.html"):
        path = root / relative
        text = path.read_text(encoding="utf-8")
        if 'id="v1-scope"' not in text:
            text = text.replace("</main>", '<h2 id="v1-scope">v1 scope</h2></main>')
            path.write_text(text, encoding="utf-8")


def install_clipboard_gate(page: Any) -> None:
    page.evaluate(
        """() => {
          let resolveCopy;
          let rejectCopy;
          const pending = new Promise((resolve, reject) => {
            resolveCopy = resolve;
            rejectCopy = reject;
          });
          Object.defineProperty(navigator, 'clipboard', {
            configurable: true,
            value: { writeText(text) { window.__copyText = text; return pending; } }
          });
          window.__copyGate = {
            resolve() { resolveCopy(); },
            reject() { rejectCopy(new Error('deliberate clipboard failure')); }
          };
        }"""
    )


def assert_clipboard_races(page: Any) -> None:
    page.goto(page.url.split("#", 1)[0] + "#recipe=skill", wait_until="networkidle")
    page.wait_for_selector("[data-playground-app]:not([hidden])")
    install_clipboard_gate(page)
    page.locator("[data-playground-copy]").click()
    checkbox = page.locator('input[type="checkbox"][value="capability.cli"]')
    checkbox.check()
    page.wait_for_function("() => location.hash.includes('include=capability.cli')")
    before = page.locator("[data-playground-status]").text_content()
    page.evaluate("() => window.__copyGate.resolve()")
    page.wait_for_timeout(0)
    after = page.locator("[data-playground-status]").text_content()
    if before != after or after == "Canonical configuration copied.":
        raise PlaygroundBrowserError(f"stale clipboard success changed selection-B status: {before!r} -> {after!r}")

    page.goto(page.url.split("#", 1)[0] + "#recipe=skill", wait_until="networkidle")
    page.wait_for_selector("[data-playground-app]:not([hidden])")
    install_clipboard_gate(page)
    page.locator("[data-playground-copy]").click()
    checkbox = page.locator('input[type="checkbox"][value="capability.cli"]')
    checkbox.check()
    page.wait_for_function("() => location.hash.includes('include=capability.cli')")
    before = page.locator("[data-playground-status]").text_content()
    page.evaluate("() => window.__copyGate.reject()")
    page.wait_for_timeout(0)
    after = page.locator("[data-playground-status]").text_content()
    if before != after or after == "Could not copy the canonical configuration.":
        raise PlaygroundBrowserError(f"stale clipboard failure changed selection-B status: {before!r} -> {after!r}")

    page.goto(page.url.split("#", 1)[0] + "#recipe=skill", wait_until="networkidle")
    page.wait_for_selector("[data-playground-app]:not([hidden])")
    install_clipboard_gate(page)
    page.locator("[data-playground-copy]").click()
    page.evaluate("() => window.__copyGate.resolve()")
    page.wait_for_function(
        "() => document.querySelector('[data-playground-status]')?.textContent === 'Canonical configuration copied.'"
    )


def assert_fragment_semantics(page: Any, base_url: str) -> None:
    page.goto(f"{base_url}playground/#v1-scope", wait_until="networkidle")
    page.wait_for_selector("[data-playground-app]:not([hidden])")
    if page.evaluate("() => location.hash") != "#v1-scope":
        raise PlaygroundBrowserError("direct ordinary heading fragment was rewritten by Playground mount")
    if page.locator("#v1-scope").count() != 1:
        raise PlaygroundBrowserError("v1-scope target is not reachable in the browser harness")
    page.locator("#v1-scope").evaluate("node => node.scrollIntoView()")
    if page.evaluate("() => location.hash") != "#v1-scope":
        raise PlaygroundBrowserError("reaching the ordinary heading target changed fragment ownership")

    markup = playground_markup() + '<h2 id="v1-scope">v1 scope</h2>'
    page.evaluate(
        """markup => {
          history.pushState({}, '', '/home/');
          document.body.innerHTML = '<main><p>Home</p></main>';
          window.document$.emit();
          history.pushState({}, '', '/playground/#v1-scope');
          document.body.innerHTML = `<main>${markup}</main>`;
          window.document$.emit();
        }""",
        markup,
    )
    page.wait_for_selector("[data-playground-app]:not([hidden])")
    if page.evaluate("() => location.hash") != "#v1-scope":
        raise PlaygroundBrowserError("instant navigation ordinary fragment was rewritten")

    page.goto(f"{base_url}playground/#recipe=skill&include=capability.cli", wait_until="networkidle")
    page.wait_for_selector("[data-playground-app]:not([hidden])")
    cli = page.locator('input[type="checkbox"][value="capability.cli"]')
    if not cli.is_checked():
        raise PlaygroundBrowserError("canonical Playground hash did not restore capability.cli")
    cli.uncheck()
    page.wait_for_function("() => location.hash === '#recipe=skill'")

    # Change the query as well as the hash so Playwright performs a fresh document
    # navigation. That exercises initial-mount fail-closed behavior rather than the
    # already-mounted hashchange status path.
    page.goto(f"{base_url}playground/?invalid-state=1#recipe=unknown", wait_until="networkidle")
    page.wait_for_function(
        "() => document.querySelector('#composition-playground')?.dataset.playgroundError === 'INVALID_SELECTION'"
    )
    if not page.locator("[data-playground-app]").is_hidden():
        raise PlaygroundBrowserError("invalid Playground-owned fragment did not fail closed")


def run_synthetic() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaygroundBrowserError("Playwright is required; install requirements-visual.txt") from exc

    with tempfile.TemporaryDirectory(prefix="composition-playground-final-browser-") as directory:
        root = Path(directory)
        prepare_harness(root)
        add_heading_anchor(root)
        server, thread, base_url, race = serve_harness(root)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                context = browser.new_context(viewport={"width": 900, "height": 800}, service_workers="block")
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                assert_fragment_semantics(page, base_url)
                page.goto(f"{base_url}playground/#recipe=skill", wait_until="networkidle")
                page.wait_for_selector("[data-playground-app]:not([hidden])")
                assert_clipboard_races(page)
                if errors:
                    raise PlaygroundBrowserError(f"focused browser regressions emitted page errors: {errors}")
                context.close()
                browser.close()
        finally:
            race.release_first.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def run_built_fragment(site_root: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaygroundBrowserError("Playwright is required; install requirements-visual.txt") from exc

    server, thread, base_url = serve_built_site(site_root)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1024, "height": 900})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{base_url}/playground/#v1-scope", wait_until="networkidle")
            page.wait_for_selector("[data-playground-app]:not([hidden])")
            if page.evaluate("() => location.hash") != "#v1-scope":
                raise PlaygroundBrowserError("built Site rewrote the real v1-scope fragment")
            if page.locator("#v1-scope").count() != 1:
                raise PlaygroundBrowserError("built Site does not expose the real v1-scope heading target")
            page.locator("#v1-scope").evaluate("node => node.scrollIntoView()")
            if page.evaluate("() => location.hash") != "#v1-scope":
                raise PlaygroundBrowserError("built Site heading target is not reachable without fragment rewrite")
            if errors:
                raise PlaygroundBrowserError(f"built Site fragment acceptance emitted page errors: {errors}")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.site_root is None:
        run_synthetic()
        print("Composition Playground final fragment/clipboard browser regressions passed")
    else:
        run_built_fragment(args.site_root)
        print("Composition Playground real built-Site fragment regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
