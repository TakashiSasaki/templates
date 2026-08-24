#!/usr/bin/env python3
"""Verify Site-local Zensical search history in a real Chromium page."""

from __future__ import annotations

import argparse
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class SearchHistoryCheckError(RuntimeError):
    """Raised when the browser search-history contract is violated."""


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return


def _wait_for_results(page: Any) -> Any:
    result = page.locator("a.md-search-result__link[href]").first
    result.wait_for(state="attached", timeout=10_000)
    return result


def _set_query(page: Any, value: str) -> None:
    page.evaluate(
        """
        (value) => {
          const input = document.querySelector('[data-md-component="search-query"]');
          if (!input) throw new Error('search query input is missing');
          input.focus();
          input.value = value;
          input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        """,
        value,
    )


def _activate_without_navigation(control: Any) -> None:
    control.evaluate(
        """
        (element) => {
          element.addEventListener('click', (event) => event.preventDefault(), { once: true });
          element.click();
        }
        """
    )


def _history(page: Any) -> list[str]:
    value = page.evaluate(
        "() => JSON.parse(localStorage.getItem('templates.search-history.v1') || '[]')"
    )
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SearchHistoryCheckError(f"stored search history is invalid: {value!r}")
    return value


def run_check(site_root: Path, output: Path | None) -> dict[str, Any]:
    root = site_root.resolve(strict=True)
    required = (
        root / "index.html",
        root / "javascripts/reader-navigation.js",
        root / "stylesheets/extra.css",
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise SearchHistoryCheckError(
            "built site is missing required search-history assets: "
            + ", ".join(path.as_posix() for path in missing)
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SearchHistoryCheckError(
            "Playwright is required for search-history browser checks"
        ) from exc

    handler = partial(QuietStaticHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    evidence: dict[str, Any] = {"base_url": base_url}

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(service_workers="block")
            page = context.new_page()
            response = page.goto(base_url + "/", wait_until="load")
            if response is None or response.status != 200:
                status = None if response is None else response.status
                raise SearchHistoryCheckError(
                    f"Site home returned {status}, expected 200"
                )

            input_locator = page.locator('[data-md-component="search-query"]')
            input_locator.wait_for(state="attached")
            page.wait_for_function(
                """
                () => document.querySelector('[data-md-component="search"]')
                  ?.dataset.siteSearchHistoryEnhanced === 'true'
                """
            )

            if _history(page):
                raise SearchHistoryCheckError("fresh browser context started with history")

            _set_query(page, "policy")
            first_result = _wait_for_results(page)
            if _history(page):
                raise SearchHistoryCheckError(
                    "search-as-you-type input was stored before result activation"
                )
            first_href = first_result.get_attribute("href")
            _activate_without_navigation(first_result)
            if _history(page) != ["policy"]:
                raise SearchHistoryCheckError(
                    f"first activated query was not stored: {_history(page)!r}"
                )

            _set_query(page, "composition")
            second_result = _wait_for_results(page)
            second_href = second_result.get_attribute("href")
            _activate_without_navigation(second_result)
            if _history(page) != ["composition", "policy"]:
                raise SearchHistoryCheckError(
                    f"second activated query did not preserve recency: {_history(page)!r}"
                )

            _set_query(page, "")
            history_section = page.locator("[data-site-search-history]")
            page.wait_for_function(
                """
                () => {
                  const section = document.querySelector('[data-site-search-history]');
                  return Boolean(section && !section.hidden);
                }
                """
            )
            history_controls = history_section.locator(
                "button[data-site-search-history-query]"
            )
            if history_controls.count() != 2:
                raise SearchHistoryCheckError(
                    f"expected 2 history controls, found {history_controls.count()}"
                )
            if history_section.locator("a.md-search-result__link").count() != 0:
                raise SearchHistoryCheckError(
                    "Site history controls leaked into Zensical result-link classes"
                )

            replay = history_section.locator(
                'button[data-site-search-history-query="policy"]'
            )
            _activate_without_navigation(replay)
            page.wait_for_function(
                """
                () => document.querySelector('[data-md-component="search-query"]')?.value === 'policy'
                """
            )
            _wait_for_results(page)
            if _history(page) != ["policy", "composition"]:
                raise SearchHistoryCheckError(
                    f"replayed history query did not move to the front: {_history(page)!r}"
                )

            page.evaluate("() => { document.documentElement.lang = 'ja'; }")
            _set_query(page, "")
            heading = history_section.locator("[data-site-search-history-heading]")
            clear = history_section.locator("[data-site-search-history-clear]")
            if (heading.text_content() or "").strip() != "最近の検索":
                raise SearchHistoryCheckError(
                    f"Japanese history heading mismatch: {heading.text_content()!r}"
                )
            if (clear.text_content() or "").strip() != "履歴を消去":
                raise SearchHistoryCheckError(
                    f"Japanese clear-history label mismatch: {clear.text_content()!r}"
                )

            _activate_without_navigation(clear)
            if _history(page):
                raise SearchHistoryCheckError("Clear history did not remove stored queries")
            if not history_section.is_hidden():
                raise SearchHistoryCheckError("empty history section remained visible")

            evidence.update(
                {
                    "first_result_href": first_href,
                    "second_result_href": second_href,
                    "stored_after_two_results": ["composition", "policy"],
                    "stored_after_replay": ["policy", "composition"],
                    "japanese_heading": "最近の検索",
                    "japanese_clear": "履歴を消去",
                    "clear_history": "passed",
                    "zensical_result_class_isolation": "passed",
                    "partial_input_not_recorded": "passed",
                }
            )
            context.close()
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
