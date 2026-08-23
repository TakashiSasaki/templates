#!/usr/bin/env python3
"""Verify localized inline Glossary chrome in a real Chromium page."""

from __future__ import annotations

import argparse
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class GlossaryLocaleChromeError(RuntimeError):
    """Raised when localized Glossary chrome does not satisfy its browser contract."""


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return


def japanese_glossary_page(site_root: Path) -> Path:
    japanese_root = site_root / "ja"
    if not japanese_root.is_dir():
        raise GlossaryLocaleChromeError("built site does not contain a Japanese reader root")
    for path in sorted(japanese_root.rglob("*.html")):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise GlossaryLocaleChromeError(f"unable to read generated page {path}: {exc}") from exc
        if '<html lang="ja"' in source and "data-glossary-id=" in source:
            return path
    raise GlossaryLocaleChromeError(
        "built site does not contain a Japanese page with an inline Glossary term"
    )


def public_path(site_root: Path, page: Path) -> str:
    relative = page.relative_to(site_root).as_posix()
    if relative == "index.html":
        return "/"
    if relative.endswith("/index.html"):
        return "/" + relative[: -len("index.html")]
    return "/" + relative


def run_check(site_root: Path, output: Path | None) -> dict[str, Any]:
    root = site_root.resolve(strict=True)
    required = (
        root / "glossary/index.json",
        root / "site-chrome-locales.json",
        root / "javascripts/glossary-inline.js",
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise GlossaryLocaleChromeError(
            "built site is missing required Glossary assets: "
            + ", ".join(path.as_posix() for path in missing)
        )
    page_path = japanese_glossary_page(root)
    route = public_path(root, page_path)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise GlossaryLocaleChromeError(
            "Playwright is required for Glossary locale chrome checks"
        ) from exc

    handler = partial(QuietStaticHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    evidence: dict[str, Any] = {
        "base_url": base_url,
        "japanese_page": page_path.relative_to(root).as_posix(),
        "route": route,
    }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(service_workers="block")
            page = context.new_page()
            response = page.goto(base_url + route, wait_until="load")
            if response is None or response.status != 200:
                status = None if response is None else response.status
                raise GlossaryLocaleChromeError(
                    f"Japanese Glossary page returned {status}, expected 200"
                )

            trigger = page.locator("button.glossary-term[data-glossary-id]").first
            trigger.wait_for(state="visible")
            trigger.click()
            dialog = page.locator("#glossary-inline-dialog")
            page.wait_for_function(
                "() => document.querySelector('#glossary-inline-dialog')?.open === true"
            )

            eyebrow = dialog.locator(".glossary-inline-dialog__eyebrow").inner_text()
            close_label = dialog.locator(".glossary-inline-dialog__close").get_attribute(
                "aria-label"
            )
            action_label = dialog.locator(
                ".glossary-inline-dialog__actions a"
            ).inner_text()
            metadata = dialog.locator(".glossary-inline-dialog__meta").inner_text()
            if eyebrow != "用語集":
                raise GlossaryLocaleChromeError(
                    f"Japanese Glossary eyebrow mismatch: {eyebrow!r}"
                )
            if close_label != "定義を閉じる":
                raise GlossaryLocaleChromeError(
                    f"Japanese Glossary close label mismatch: {close_label!r}"
                )
            if action_label != "用語集で開く":
                raise GlossaryLocaleChromeError(
                    f"Japanese Glossary action label mismatch: {action_label!r}"
                )
            if not (
                metadata.startswith("外部用語 · 整理:")
                or metadata.startswith("テンプレート定義 ·")
            ):
                raise GlossaryLocaleChromeError(
                    f"Japanese Glossary metadata was not localized: {metadata!r}"
                )
            evidence["japanese"] = {
                "eyebrow": eyebrow,
                "close_label": close_label,
                "action_label": action_label,
                "metadata": metadata,
            }

            dialog.locator(".glossary-inline-dialog__close").click()
            page.wait_for_function(
                "() => document.querySelector('#glossary-inline-dialog')?.open === false"
            )
            page.evaluate("() => { document.documentElement.lang = 'de'; }")
            trigger.click()
            page.wait_for_function(
                "() => document.querySelector('#glossary-inline-dialog')?.open === true"
            )
            fallback_eyebrow = dialog.locator(
                ".glossary-inline-dialog__eyebrow"
            ).inner_text()
            fallback_action = dialog.locator(
                ".glossary-inline-dialog__actions a"
            ).inner_text()
            if fallback_eyebrow != "Glossary" or fallback_action != "Open in Glossary":
                raise GlossaryLocaleChromeError(
                    "unregistered Glossary locale did not fall back to canonical English: "
                    f"eyebrow={fallback_eyebrow!r}, action={fallback_action!r}"
                )
            evidence["unregistered_locale"] = {
                "eyebrow": fallback_eyebrow,
                "action_label": fallback_action,
            }
            context.close()

            fallback_context = browser.new_context(service_workers="block")
            fallback_page = fallback_context.new_page()
            fallback_page.route(
                "**/site-chrome-locales.json",
                lambda intercepted: intercepted.abort(),
            )
            response = fallback_page.goto(base_url + route, wait_until="load")
            if response is None or response.status != 200:
                status = None if response is None else response.status
                raise GlossaryLocaleChromeError(
                    f"fallback Glossary page returned {status}, expected 200"
                )
            fallback_trigger = fallback_page.locator(
                "button.glossary-term[data-glossary-id]"
            ).first
            fallback_trigger.wait_for(state="visible")
            original_href = fallback_trigger.get_attribute("data-glossary-href")
            fallback_trigger.click()
            restored = fallback_page.locator(
                "a.glossary-term[data-glossary-id]"
            ).first
            restored.wait_for(state="visible")
            restored_href = restored.get_attribute("href")
            if not original_href or restored_href != original_href:
                raise GlossaryLocaleChromeError(
                    "Glossary locale failure did not restore the static link fallback"
                )
            if fallback_page.locator("#glossary-inline-dialog[open]").count() != 0:
                raise GlossaryLocaleChromeError(
                    "Glossary locale failure opened a dialog instead of restoring fallback"
                )
            evidence["locale_failure_restored_link"] = restored_href
            fallback_context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evidence = run_check(args.site_root, args.output)
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
