#!/usr/bin/env python3
"""Verify Site-local search history against Zensical's real Shadow DOM search UI."""

from __future__ import annotations

import argparse
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


class SearchHistoryCheckError(RuntimeError):
    """Raised when the browser search-history contract is violated."""


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return


SEARCH_ROOT_EXPRESSION = """
() => Array.from(document.body.children)
  .map((host) => host.shadowRoot)
  .find((root) => root && root.querySelector('input[role="combobox"]')) || null
"""


def _search_contract_snapshot(page: Any) -> dict[str, Any]:
    return page.evaluate(
        f"""
        () => {{
          const hosts = Array.from(document.body.children).filter((host) => host.shadowRoot);
          const searchRoots = hosts
            .map((host) => host.shadowRoot)
            .filter((root) => root.querySelector('input[role="combobox"]'));
          const root = ({SEARCH_ROOT_EXPRESSION})();
          const input = root?.querySelector('input[role="combobox"]');
          const inputRect = input?.getBoundingClientRect();
          const inputStyle = input ? getComputedStyle(input) : null;
          const ancestors = [];
          for (let element = input; element; element = element.parentElement) {{
            const style = getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            ancestors.push({{
              tag: element.tagName,
              className: String(element.className || ''),
              display: style.display,
              visibility: style.visibility,
              opacity: style.opacity,
              pointerEvents: style.pointerEvents,
              transform: style.transform,
              overflow: style.overflow,
              rect: {{ x: rect.x, y: rect.y, width: rect.width, height: rect.height }},
            }});
          }}
          return {{
            generator: document.querySelector('meta[name="generator"]')?.content || null,
            lightSearchRoots: document.querySelectorAll('[data-md-component="search"]').length,
            openShadowHosts: hosts.length,
            shadowComboboxes: searchRoots.reduce(
              (count, candidate) =>
                count + candidate.querySelectorAll('input[role="combobox"]').length,
              0,
            ),
            focusedShadowComboboxes: searchRoots.reduce((count, candidate) => {{
              const candidateInput = candidate.querySelector('input[role="combobox"]');
              return count + (candidateInput && candidate.activeElement === candidateInput ? 1 : 0);
            }}, 0),
            input: input
              ? {{
                  value: input.value,
                  display: inputStyle.display,
                  visibility: inputStyle.visibility,
                  opacity: inputStyle.opacity,
                  pointerEvents: inputStyle.pointerEvents,
                  rect: {{
                    x: inputRect.x,
                    y: inputRect.y,
                    width: inputRect.width,
                    height: inputRect.height,
                  }},
                  clientRects: input.getClientRects().length,
                  checkVisibility:
                    typeof input.checkVisibility === 'function' ? input.checkVisibility() : null,
                }}
              : null,
            ancestors,
          }};
        }}
        """
    )


def _wait_for_search_contract(page: Any) -> None:
    try:
        page.wait_for_function(
            """
            () => Array.from(document.body.children).some(
              (host) => host.shadowRoot?.querySelector('input[role="combobox"]')
            )
            """,
            timeout=10_000,
        )
    except Exception as exc:
        snapshot = _search_contract_snapshot(page)
        raise SearchHistoryCheckError(
            "Zensical search integration contract changed: expected one direct body child "
            "with an open Shadow Root containing input[role=combobox]; "
            f"observed {snapshot}"
        ) from exc

    snapshot = _search_contract_snapshot(page)
    if snapshot["lightSearchRoots"] != 1 or snapshot["shadowComboboxes"] != 1:
        raise SearchHistoryCheckError(
            "Zensical search integration contract is ambiguous: "
            + json.dumps(snapshot, sort_keys=True)
        )


def _input(page: Any) -> Any:
    locator = page.locator('input[role="combobox"]').first
    locator.wait_for(state="attached", timeout=10_000)
    return locator


def _input_is_actionable(search_input: Any, timeout: int = 500) -> bool:
    """Use Playwright actionability without actually clicking the input."""
    try:
        search_input.click(trial=True, timeout=timeout)
        return True
    except Exception:
        return False


def _open_search(page: Any) -> None:
    """Ensure the Shadow DOM combobox can actually receive a user pointer action."""
    _wait_for_search_contract(page)
    search_input = _input(page)
    if _input_is_actionable(search_input):
        return

    trigger = page.locator('[data-md-component="search"] button').first
    try:
        trigger.wait_for(state="visible", timeout=5_000)
        trigger.click()
        search_input.click(trial=True, timeout=10_000)
    except Exception as exc:
        snapshot = _search_contract_snapshot(page)
        raise SearchHistoryCheckError(
            "Zensical search did not expose an actionable Shadow DOM combobox after activation; "
            f"observed {snapshot}"
        ) from exc


def _wait_for_result(page: Any) -> str:
    page.wait_for_function(
        f"""
        () => {{
          const root = ({SEARCH_ROOT_EXPRESSION})();
          return Boolean(root?.querySelector('ol a[href]'));
        }}
        """,
        timeout=10_000,
    )
    href = page.evaluate(
        f"""
        () => {{
          const root = ({SEARCH_ROOT_EXPRESSION})();
          const anchor = root?.querySelector('ol a[href]');
          return anchor?.getAttribute('href') || null;
        }}
        """
    )
    if not isinstance(href, str) or not href:
        raise SearchHistoryCheckError("Zensical produced a result without a usable href")
    return href


def _activate_first_result_without_navigation(page: Any) -> str:
    """Activate a real result but suppress navigation so the same page can inspect storage."""
    href = _wait_for_result(page)
    activated = page.evaluate(
        f"""
        () => {{
          const root = ({SEARCH_ROOT_EXPRESSION})();
          const anchor = root?.querySelector('ol a[href]');
          if (!(anchor instanceof HTMLAnchorElement)) return false;
          anchor.addEventListener('click', (event) => event.preventDefault(), {{ once: true }});
          anchor.click();
          return true;
        }}
        """
    )
    if not activated:
        raise SearchHistoryCheckError("unable to activate the first Zensical search result")
    return href


def _history(page: Any) -> list[str]:
    value = page.evaluate(
        "() => JSON.parse(localStorage.getItem('templates.search-history.v1') || '[]')"
    )
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SearchHistoryCheckError(f"stored search history is invalid: {value!r}")
    return value


def _history_snapshot(page: Any) -> dict[str, Any]:
    return page.evaluate(
        f"""
        () => {{
          const root = ({SEARCH_ROOT_EXPRESSION})();
          const section = root?.querySelector('[data-site-search-history]');
          return {{
            connected: Boolean(section?.isConnected),
            visible: Boolean(section && !section.hidden),
            heading:
              section?.querySelector('[data-site-search-history-heading]')?.textContent?.trim() || '',
            clear:
              section?.querySelector('[data-site-search-history-clear]')?.textContent?.trim() || '',
            queries: Array.from(
              section?.querySelectorAll('[data-site-search-history-query]') || []
            ).map((button) => button.textContent.trim()),
            resultAnchorsInsideHistory: section?.querySelectorAll('a[href]').length || 0,
          }};
        }}
        """
    )


def _replay_snapshot(page: Any) -> dict[str, Any]:
    try:
        actionable = _input_is_actionable(_input(page))
    except Exception as exc:
        actionable = f"unavailable: {type(exc).__name__}: {exc}"
    result_state = page.evaluate(
        f"""
        () => {{
          const root = ({SEARCH_ROOT_EXPRESSION})();
          const anchors = Array.from(root?.querySelectorAll('ol a[href]') || []);
          return {{
            count: anchors.length,
            hrefs: anchors.slice(0, 5).map((anchor) => anchor.getAttribute('href')),
          }};
        }}
        """
    )
    return {
        "stored": _history(page),
        "history": _history_snapshot(page),
        "search": _search_contract_snapshot(page),
        "input_actionable": actionable,
        "results": result_state,
    }


def _wait_for_history_visible(page: Any) -> None:
    try:
        page.wait_for_function(
            f"""
            () => {{
              const root = ({SEARCH_ROOT_EXPRESSION})();
              const section = root?.querySelector('[data-site-search-history]');
              return Boolean(section && !section.hidden);
            }}
            """,
            timeout=5_000,
        )
    except Exception as exc:
        raise SearchHistoryCheckError(
            "Site search history did not become visible; "
            f"search={_search_contract_snapshot(page)!r}, "
            f"history={_history_snapshot(page)!r}, stored={_history(page)!r}"
        ) from exc


def _fill(page: Any, value: str) -> None:
    _open_search(page)
    search_input = _input(page)
    try:
        search_input.fill(value, timeout=10_000)
    except Exception as exc:
        snapshot = _search_contract_snapshot(page)
        raise SearchHistoryCheckError(
            f"actionable Zensical search input became unusable before fill({value!r}); "
            f"observed {snapshot}"
        ) from exc


def run_check(site_root: Path, output: Path | None) -> dict[str, Any]:
    root = site_root.resolve(strict=True)
    required = (
        root / "index.html",
        root / "javascripts/search-history.js",
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
    requests: list[tuple[str, str]] = []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(service_workers="block")
            page = context.new_page()
            page.on(
                "request",
                lambda request: requests.append((request.url, request.post_data or "")),
            )
            response = page.goto(base_url + "/", wait_until="load")
            if response is None or response.status != 200:
                status = None if response is None else response.status
                raise SearchHistoryCheckError(f"Site home returned {status}, expected 200")

            _wait_for_search_contract(page)
            contract = _search_contract_snapshot(page)
            if _history(page):
                raise SearchHistoryCheckError("fresh browser context started with history")

            _fill(page, "policy")
            _wait_for_result(page)
            if _history(page):
                raise SearchHistoryCheckError(
                    "search-as-you-type input was stored before result activation"
                )
            first_href = _activate_first_result_without_navigation(page)
            if _history(page) != ["policy"]:
                raise SearchHistoryCheckError(
                    f"first activated query was not stored: {_history(page)!r}"
                )

            _fill(page, "composition")
            second_href = _activate_first_result_without_navigation(page)
            if _history(page) != ["composition", "policy"]:
                raise SearchHistoryCheckError(
                    f"second activated query did not preserve recency: {_history(page)!r}"
                )

            _fill(page, "")
            _wait_for_history_visible(page)
            history = _history_snapshot(page)
            if history["queries"] != ["composition", "policy"]:
                raise SearchHistoryCheckError(
                    f"history controls do not reflect MRU order: {history!r}"
                )
            if history["resultAnchorsInsideHistory"] != 0:
                raise SearchHistoryCheckError(
                    "Site history controls leaked into Zensical/result anchor semantics"
                )

            page.evaluate(
                f"""
                () => {{
                  const root = ({SEARCH_ROOT_EXPRESSION})();
                  const input = root?.querySelector('input[role="combobox"]');
                  window.__siteSearchHistoryReplayInputEvents = 0;
                  input?.addEventListener(
                    'input',
                    () => {{ window.__siteSearchHistoryReplayInputEvents += 1; }},
                    {{ once: true }},
                  );
                }}
                """
            )
            replay = page.locator('button[data-site-search-history-query="policy"]').first
            try:
                replay.click(timeout=5_000)
                page.wait_for_function(
                    f"""
                    () => {{
                      const root = ({SEARCH_ROOT_EXPRESSION})();
                      return root?.querySelector('input[role="combobox"]')?.value === 'policy';
                    }}
                    """,
                    timeout=5_000,
                )
            except Exception as exc:
                raise SearchHistoryCheckError(
                    "replay did not update the Zensical combobox; "
                    + json.dumps(_replay_snapshot(page), ensure_ascii=False, sort_keys=True)
                ) from exc
            replay_input_events = page.evaluate(
                "() => window.__siteSearchHistoryReplayInputEvents || 0"
            )
            if replay_input_events < 1:
                raise SearchHistoryCheckError(
                    "replay updated the query without an observed input event; "
                    + json.dumps(_replay_snapshot(page), ensure_ascii=False, sort_keys=True)
                )
            try:
                _wait_for_result(page)
            except Exception as exc:
                raise SearchHistoryCheckError(
                    "replay updated the query but did not regenerate Zensical results; "
                    + json.dumps(_replay_snapshot(page), ensure_ascii=False, sort_keys=True)
                ) from exc
            if _history(page) != ["policy", "composition"]:
                raise SearchHistoryCheckError(
                    f"replayed query did not move to the front: {_history(page)!r}"
                )

            page.evaluate("() => { document.documentElement.lang = 'ja'; }")
            _fill(page, "")
            _wait_for_history_visible(page)
            japanese = _history_snapshot(page)
            if japanese["heading"] != "最近の検索" or japanese["clear"] != "履歴を消去":
                raise SearchHistoryCheckError(
                    f"Japanese search-history chrome mismatch: {japanese!r}"
                )

            clear = page.locator("button[data-site-search-history-clear]").first
            clear.click()
            if _history(page):
                raise SearchHistoryCheckError("Clear history did not remove stored queries")
            cleared = _history_snapshot(page)
            if cleared["visible"]:
                raise SearchHistoryCheckError("empty history section remained visible")

            # Cross-tab storage events must update an already-open search UI without reload.
            page.evaluate("() => { document.documentElement.lang = 'en'; }")
            peer = context.new_page()
            peer_response = peer.goto(base_url + "/", wait_until="load")
            if peer_response is None or peer_response.status != 200:
                raise SearchHistoryCheckError("peer page for storage-event check did not load")
            peer.evaluate(
                "() => localStorage.setItem('templates.search-history.v1', JSON.stringify(['policy']))"
            )
            _wait_for_history_visible(page)
            cross_tab = _history_snapshot(page)
            if cross_tab["queries"] != ["policy"]:
                raise SearchHistoryCheckError(
                    f"cross-tab storage update was not rendered: {cross_tab!r}"
                )
            peer.close()

            for url, post_data in requests:
                query = unquote(urlsplit(url).query).lower()
                body = unquote(post_data).lower()
                if (
                    "policy" in query
                    or "composition" in query
                    or "policy" in body
                    or "composition" in body
                ):
                    raise SearchHistoryCheckError(
                        "search term leaked into a network request payload: " + url
                    )

            evidence.update(
                {
                    "zensical_contract": contract,
                    "first_result_href": first_href,
                    "second_result_href": second_href,
                    "stored_after_two_results": ["composition", "policy"],
                    "stored_after_replay": ["policy", "composition"],
                    "replay_input_events": replay_input_events,
                    "japanese_heading": japanese["heading"],
                    "japanese_clear": japanese["clear"],
                    "cross_tab_queries": cross_tab["queries"],
                    "actionability_gate": "passed",
                    "clear_history": "passed",
                    "partial_input_not_recorded": "passed",
                    "query_network_leak": "not observed",
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
