#!/usr/bin/env python3
"""Chromium regressions for the final three Composition Playground review findings."""

from __future__ import annotations

import gzip
import json
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

SELECTION_ERROR_STATUS = "The Playground selection in this URL is malformed and was rejected."
LOADED_STATUS = "Canonical Composition projection loaded with exact Site publication provenance."
COPIED_STATUS = "Canonical configuration copied."
COPY_FAILED_STATUS = "Could not copy the canonical configuration."


def assert_selection_failure(page: Any) -> None:
    page.wait_for_function(
        "() => document.querySelector('#composition-playground')?.dataset.playgroundError === 'INVALID_SELECTION'"
    )
    root = page.locator("#composition-playground")
    if root.get_attribute("data-playground-error") != "INVALID_SELECTION":
        raise PlaygroundBrowserError("invalid selection did not preserve machine-visible INVALID_SELECTION identity")
    if not page.locator("[data-playground-app]").is_hidden():
        raise PlaygroundBrowserError("invalid selection did not hide the core application")
    if not page.locator("[data-playground-explain]").is_hidden():
        raise PlaygroundBrowserError("invalid selection did not hide explainability through shared failure state")
    status = page.locator("[data-playground-status]").text_content() or ""
    if status != SELECTION_ERROR_STATUS:
        raise PlaygroundBrowserError(f"invalid selection used the wrong visible status: {status!r}")
    lowered = status.lower()
    if "projection" in lowered or "provenance" in lowered:
        raise PlaygroundBrowserError("invalid selection was falsely presented as provider/provenance corruption")


def current_mount_state(page: Any) -> Any:
    return page.evaluate(
        """async () => {
          const context = await window.CompositionPlayground.ensureMounted(document);
          return context ? { recipeId: context.state.recipeId, includes: context.state.includes } : null;
        }"""
    )


def assert_selection_error_paths(page: Any, base_url: str) -> None:
    # An initially invalid owned hash must fail closed but still install the
    # same-document recovery path. Repeated mounts must expose the live state,
    # not the context from the initial mount promise.
    page.goto(f"{base_url}playground/?initial-invalid=1#recipe=unknown", wait_until="networkidle")
    assert_selection_failure(page)
    if current_mount_state(page) is not None:
        raise PlaygroundBrowserError("initial invalid selection exposed a stale validated context")

    page.evaluate("() => { location.hash = '#recipe=skill'; }")
    page.wait_for_selector("[data-playground-app]:not([hidden])")
    page.wait_for_selector("[data-playground-explain]:not([hidden])")
    recovered = current_mount_state(page)
    if recovered != {"recipeId": "skill", "includes": []}:
        raise PlaygroundBrowserError(f"initial invalid selection did not recover in the same document: {recovered!r}")

    page.evaluate("() => { location.hash = '#recipe=skill&include=capability.cli'; }")
    page.wait_for_function(
        """() => document.querySelector('[data-playground-config]')?.textContent.includes('capability.cli')"""
    )
    changed = current_mount_state(page)
    if changed != {"recipeId": "skill", "includes": ["capability.cli"]}:
        raise PlaygroundBrowserError(f"repeated mount returned stale selection context: {changed!r}")

    page.evaluate("() => { location.hash = '#recipe=unknown'; }")
    assert_selection_failure(page)
    if current_mount_state(page) is not None:
        raise PlaygroundBrowserError("repeated mount returned a prior context after same-document fail-close")

    page.evaluate("() => { location.hash = '#recipe=skill&include=capability.cli'; }")
    page.wait_for_selector("[data-playground-app]:not([hidden])")
    page.wait_for_selector("[data-playground-explain]:not([hidden])")
    page.wait_for_function(
        """() => !document.querySelector('#composition-playground')?.dataset.playgroundError &&
        document.querySelector('[data-playground-status]')?.textContent ===
          'Canonical Composition projection loaded with exact Site publication provenance.'"""
    )

    page.evaluate("() => { location.hash = '#recipe=unknown'; }")
    assert_selection_failure(page)
    page.evaluate("() => { location.hash = '#v1-scope'; }")
    page.wait_for_selector("[data-playground-app]:not([hidden])")
    page.wait_for_selector("[data-playground-explain]:not([hidden])")
    if page.evaluate("() => location.hash") != "#v1-scope":
        raise PlaygroundBrowserError("ordinary document fragment recovery rewrote fragment ownership")
    if page.locator("[data-playground-status]").text_content() != LOADED_STATUS:
        raise PlaygroundBrowserError("ordinary fragment recovery left selection-error feedback visible")


def install_clipboard_attempt_controller(page: Any) -> None:
    page.evaluate(
        """() => {
          window.__copyAttempts = [];
          Object.defineProperty(navigator, 'clipboard', {
            configurable: true,
            value: {
              writeText(text) {
                return new Promise((resolve, reject) => {
                  window.__copyAttempts.push({ text, resolve, reject });
                });
              }
            }
          });
          window.__copyControl = {
            count() { return window.__copyAttempts.length; },
            resolve(index) { window.__copyAttempts[index].resolve(); },
            reject(index) { window.__copyAttempts[index].reject(new Error(`copy ${index} failed`)); }
          };
        }"""
    )


def start_two_copy_attempts(page: Any) -> None:
    install_clipboard_attempt_controller(page)
    page.locator("[data-playground-copy]").click()
    page.locator("[data-playground-copy]").click()
    page.wait_for_function("() => window.__copyControl?.count() === 2")


def assert_copy_attempt_ownership(page: Any, base_url: str) -> None:
    # Case A: newer success owns feedback; an older later failure is a no-op.
    page.goto(f"{base_url}playground/?copy-case=a#recipe=skill", wait_until="networkidle")
    page.wait_for_selector("[data-playground-app]:not([hidden])")
    start_two_copy_attempts(page)
    page.evaluate("() => window.__copyControl.resolve(1)")
    page.wait_for_function(
        "() => document.querySelector('[data-playground-status]')?.textContent === 'Canonical configuration copied.'"
    )
    page.evaluate("() => window.__copyControl.reject(0)")
    page.wait_for_timeout(0)
    if page.locator("[data-playground-status]").text_content() != COPIED_STATUS:
        raise PlaygroundBrowserError("older copy failure overwrote newer successful feedback")

    # Case B: newer failure owns feedback; an older later success is a no-op.
    page.goto(f"{base_url}playground/?copy-case=b#recipe=skill", wait_until="networkidle")
    page.wait_for_selector("[data-playground-app]:not([hidden])")
    start_two_copy_attempts(page)
    page.evaluate("() => window.__copyControl.reject(1)")
    page.wait_for_function(
        "() => document.querySelector('[data-playground-status]')?.textContent === 'Could not copy the canonical configuration.'"
    )
    page.evaluate("() => window.__copyControl.resolve(0)")
    page.wait_for_timeout(0)
    if page.locator("[data-playground-status]").text_content() != COPY_FAILED_STATUS:
        raise PlaygroundBrowserError("older copy success overwrote newer failed feedback")

    # Case C: the superseded attempt completes before the latest one. It must
    # remain silent until the latest attempt publishes its result.
    page.goto(f"{base_url}playground/?copy-case=c#recipe=skill", wait_until="networkidle")
    page.wait_for_selector("[data-playground-app]:not([hidden])")
    start_two_copy_attempts(page)
    before = page.locator("[data-playground-status]").text_content()
    page.evaluate("() => window.__copyControl.resolve(0)")
    page.wait_for_timeout(0)
    after_old = page.locator("[data-playground-status]").text_content()
    if before != after_old or after_old in {COPIED_STATUS, COPY_FAILED_STATUS}:
        raise PlaygroundBrowserError("superseded copy attempt published user-visible feedback")
    page.evaluate("() => window.__copyControl.resolve(1)")
    page.wait_for_function(
        "() => document.querySelector('[data-playground-status]')?.textContent === 'Canonical configuration copied.'"
    )


def inject_resolved_conflict(root: Path) -> None:
    projection_path = root / "composition" / "playground" / "composition-playground-v1.json.gz"
    raw = json.loads(gzip.decompress(projection_path.read_bytes()))
    outcome = next(
        (item for item in raw["outcomes"] if len(item.get("resolved_components", [])) >= 2),
        None,
    )
    if outcome is None:
        raise PlaygroundBrowserError("conflict regression fixture has no multi-component resolved outcome")
    source_id, target_id = outcome["resolved_components"][:2]
    source = next((item for item in raw["components"] if item.get("id") == source_id), None)
    if source is None:
        raise PlaygroundBrowserError("conflict regression could not resolve the source component")
    conflicts = list(source.get("conflicts", []))
    if target_id not in conflicts:
        conflicts.append(target_id)
    source["conflicts"] = conflicts
    projection_path.write_bytes(
        gzip.compress(json.dumps(raw, separators=(",", ":")).encode("utf-8"), compresslevel=9, mtime=0)
    )


def assert_conflicting_outcome_rejected(browser: Any, root: Path, base_url: str) -> None:
    inject_resolved_conflict(root)
    context = browser.new_context(viewport={"width": 900, "height": 800}, service_workers="block")
    page = context.new_page()
    try:
        page.goto(f"{base_url}playground/?conflict=1#recipe=skill", wait_until="networkidle")
        page.wait_for_function(
            "() => document.querySelector('#composition-playground')?.dataset.playgroundError === 'MALFORMED_PROJECTION'"
        )
        if not page.locator("[data-playground-app]").is_hidden():
            raise PlaygroundBrowserError("conflicting resolved outcome exposed the core application")
        if not page.locator("[data-playground-explain]").is_hidden():
            raise PlaygroundBrowserError("conflicting resolved outcome exposed explainability")
        context_value = page.evaluate("() => window.CompositionPlayground.ensureMounted(document)")
        if context_value is not None:
            raise PlaygroundBrowserError("conflicting resolved outcome exposed a validated shared context")
    finally:
        context.close()


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaygroundBrowserError("Playwright is required; install requirements-visual.txt") from exc

    with tempfile.TemporaryDirectory(prefix="composition-playground-final-three-browser-") as directory:
        root = Path(directory)
        prepare_harness(root)
        server, thread, base_url, race = serve_harness(root)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                context = browser.new_context(viewport={"width": 900, "height": 800}, service_workers="block")
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                assert_selection_error_paths(page, base_url)
                assert_copy_attempt_ownership(page, base_url)
                if errors:
                    raise PlaygroundBrowserError(f"final-three browser regressions emitted page errors: {errors}")
                context.close()

                assert_conflicting_outcome_rejected(browser, root, base_url)
                browser.close()
        finally:
            race.release_first.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    print("Composition Playground final three Chromium regressions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
