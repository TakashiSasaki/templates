#!/usr/bin/env python3
"""Desktop grid geometry regressions for Composition Playground explainability."""

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
    prepare_harness,
    serve as serve_harness,
)
from check_composition_playground_cross_authority import serve as serve_built_site


def assert_desktop_geometry(page: Any) -> None:
    metrics = page.evaluate(
        """() => {
          const rect = (selector) => {
            const node = document.querySelector(selector);
            if (!node) return null;
            const value = node.getBoundingClientRect();
            return { left: value.left, right: value.right, top: value.top, width: value.width };
          };
          return {
            innerWidth: window.innerWidth,
            clientWidth: document.documentElement.clientWidth,
            scrollWidth: document.documentElement.scrollWidth,
            app: rect('[data-playground-app]'),
            explain: rect('[data-playground-explain]'),
            selection: rect('[aria-labelledby="playground-selection-title"]'),
            result: rect('[aria-labelledby="playground-result-title"]'),
            appHidden: document.querySelector('[data-playground-app]')?.hidden ?? true,
            explainHidden: document.querySelector('[data-playground-explain]')?.hidden ?? true,
          };
        }"""
    )
    if metrics["innerWidth"] < 960 or metrics["clientWidth"] < 960:
        raise PlaygroundBrowserError(f"desktop geometry ran below the 60rem breakpoint: {metrics}")
    if metrics["scrollWidth"] > metrics["clientWidth"] + 1:
        raise PlaygroundBrowserError(f"desktop Playground introduced horizontal overflow: {metrics}")
    if metrics["appHidden"] or metrics["explainHidden"]:
        raise PlaygroundBrowserError(f"desktop Playground views did not become visible: {metrics}")

    app = metrics["app"]
    explain = metrics["explain"]
    selection = metrics["selection"]
    result = metrics["result"]
    if not all((app, explain, selection, result)):
        raise PlaygroundBrowserError(f"desktop geometry could not resolve required sections: {metrics}")

    tolerance = 2
    if abs(explain["left"] - app["left"]) > tolerance or abs(explain["right"] - app["right"]) > tolerance:
        raise PlaygroundBrowserError(f"explainability does not span the full desktop grid: {metrics}")
    if explain["width"] < app["width"] - tolerance:
        raise PlaygroundBrowserError(f"explainability remains constrained to one desktop column: {metrics}")
    if selection["width"] >= app["width"] - tolerance or result["width"] >= app["width"] - tolerance:
        raise PlaygroundBrowserError(f"desktop two-column selection/result layout was lost: {metrics}")
    if abs(selection["top"] - result["top"]) > tolerance:
        raise PlaygroundBrowserError(f"desktop selection/result sections are not sharing the grid row: {metrics}")
    for name, section in (("selection", selection), ("result", result), ("explain", explain)):
        if section["left"] < app["left"] - tolerance or section["right"] > app["right"] + tolerance:
            raise PlaygroundBrowserError(f"desktop {name} section escapes the Playground grid: {metrics}")


def run_synthetic() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaygroundBrowserError("Playwright is required; install requirements-visual.txt") from exc

    with tempfile.TemporaryDirectory(prefix="composition-playground-final-grid-") as directory:
        root = Path(directory)
        prepare_harness(root)
        server, thread, base_url, race = serve_harness(root)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome")
                context = browser.new_context(viewport={"width": 1024, "height": 900}, service_workers="block")
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"{base_url}playground/#recipe=skill", wait_until="networkidle")
                page.wait_for_selector("[data-playground-app]:not([hidden])")
                page.wait_for_selector("[data-playground-explain]:not([hidden])")
                assert_desktop_geometry(page)
                if errors:
                    raise PlaygroundBrowserError(f"synthetic desktop grid acceptance emitted page errors: {errors}")
                context.close()
                browser.close()
        finally:
            race.release_first.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def run_built(site_root: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaygroundBrowserError("Playwright is required; install requirements-visual.txt") from exc

    server, thread, base_url = serve_built_site(site_root)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome")
            page = browser.new_page(viewport={"width": 1280, "height": 1000})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{base_url.rstrip('/')}/playground/#recipe=skill", wait_until="networkidle")
            page.wait_for_selector("[data-playground-app]:not([hidden])")
            page.wait_for_selector("[data-playground-explain]:not([hidden])")
            assert_desktop_geometry(page)
            if errors:
                raise PlaygroundBrowserError(f"built Site desktop grid acceptance emitted page errors: {errors}")
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
        print("Composition Playground synthetic desktop grid regression passed")
    else:
        run_built(args.site_root)
        print("Composition Playground built-Site desktop grid regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
