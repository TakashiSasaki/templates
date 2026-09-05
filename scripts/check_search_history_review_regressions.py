#!/usr/bin/env python3
"""Focused Chromium regressions for Site search-history review findings."""
from __future__ import annotations

import argparse
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

KEY = "templates.search-history.v1"
PENDING_KEY = "templates.search-history.pending-enter.v1"
ROOT_EXPR = """Array.from(document.body.children).map((host) => host.shadowRoot).find((root) => root && root.querySelector('input[role=\"combobox\"]')) || null"""
HISTORY_ROOT_EXPR = """Array.from(document.body.children).map((host) => host.shadowRoot).find((root) => root && root.querySelector('[data-site-search-history]')) || null"""


class CheckError(RuntimeError):
    pass


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return


def history(page: Any) -> list[str]:
    return page.evaluate(f"() => JSON.parse(localStorage.getItem({KEY!r}) || '[]')")


def input_locator(page: Any) -> Any:
    locator = page.locator('input[role="combobox"]').first
    locator.wait_for(state="attached", timeout=10_000)
    return locator


def open_search(page: Any) -> Any:
    search_input = input_locator(page)
    try:
        search_input.click(trial=True, timeout=500)
        return search_input
    except Exception:
        trigger = page.locator('[data-md-component="search"] button').first
        trigger.click(timeout=5_000)
        search_input.click(trial=True, timeout=10_000)
        return search_input


def fill(page: Any, value: str) -> None:
    open_search(page).fill(value, timeout=10_000)


def result_signature(page: Any) -> list[str]:
    return page.evaluate(
        f"""() => {{
          const root = {ROOT_EXPR};
          return Array.from(root?.querySelectorAll('ol a[href]') || [])
            .map((anchor) => `${{anchor.getAttribute('href')}}|${{anchor.textContent?.trim() || ''}}`);
        }}"""
    )


def wait_results(page: Any) -> list[str]:
    page.wait_for_function(
        f"""() => {{ const root = {ROOT_EXPR}; return Boolean(root?.querySelector('ol a[href]')); }}""",
        timeout=10_000,
    )
    return result_signature(page)


def pointer_activate_without_navigation(page: Any) -> str:
    """Use a trusted pointer click while suppressing only its default navigation."""
    wait_results(page)
    result = page.locator('ol a[href]').first
    href = result.evaluate("(anchor) => anchor.href")
    page.evaluate(
        f"""() => {{
          const root = {ROOT_EXPR};
          root?.addEventListener(
            'click',
            (event) => {{
              const target = event.target instanceof Element ? event.target.closest('a[href]') : null;
              if (target?.closest('ol')) event.preventDefault();
            }},
            {{ capture: true, once: true }},
          );
        }}"""
    )
    result.click(timeout=5_000)
    return href


def wait_history_visible(page: Any) -> None:
    page.wait_for_function(
        f"""() => {{
          const root = {HISTORY_ROOT_EXPR};
          const section = root?.querySelector('[data-site-search-history]');
          return Boolean(section && !section.hidden);
        }}""",
        timeout=5_000,
    )


def clean_navigation_key(url: str) -> str:
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "h"]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def install_write_counter(page: Any) -> None:
    page.evaluate(
        f"""() => {{
          sessionStorage.setItem('__siteSearchHistoryWriteCount', '0');
          const original = Storage.prototype.setItem;
          Storage.prototype.setItem = function(key, value) {{
            if (this === localStorage && key === {KEY!r}) {{
              const count = Number(sessionStorage.getItem('__siteSearchHistoryWriteCount') || '0');
              original.call(sessionStorage, '__siteSearchHistoryWriteCount', String(count + 1));
            }}
            return original.call(this, key, value);
          }};
        }}"""
    )


def install_no_navigation_api(context: Any) -> None:
    """Force the runtime's standards-based non-Navigation-API branch before Site scripts run."""
    context.add_init_script(
        f"""
        (() => {{
          Object.defineProperty(window, 'navigation', {{
            configurable: true,
            enumerable: false,
            writable: false,
            value: undefined,
          }});
          const original = Storage.prototype.setItem;
          Storage.prototype.setItem = function(key, value) {{
            if (this === localStorage && key === {KEY!r}) {{
              const count = Number(sessionStorage.getItem('__siteSearchHistoryWriteCount') || '0');
              original.call(sessionStorage, '__siteSearchHistoryWriteCount', String(count + 1));
            }}
            if (this === sessionStorage && key === {PENDING_KEY!r}) {{
              const count = Number(sessionStorage.getItem('__siteSearchHistoryPendingWriteCount') || '0');
              original.call(sessionStorage, '__siteSearchHistoryPendingWriteCount', String(count + 1));
            }}
            return original.call(this, key, value);
          }};
          if (sessionStorage.getItem('__siteSearchHistoryWriteCount') === null) {{
            original.call(sessionStorage, '__siteSearchHistoryWriteCount', '0');
          }}
          if (sessionStorage.getItem('__siteSearchHistoryPendingWriteCount') === null) {{
            original.call(sessionStorage, '__siteSearchHistoryPendingWriteCount', '0');
          }}
        }})();
        """
    )


def write_count(page: Any) -> int:
    return int(page.evaluate("() => sessionStorage.getItem('__siteSearchHistoryWriteCount') || '0'"))


def pending_write_count(page: Any) -> int:
    return int(page.evaluate("() => sessionStorage.getItem('__siteSearchHistoryPendingWriteCount') || '0'"))


def pending_record(page: Any) -> str | None:
    return page.evaluate(f"() => sessionStorage.getItem({PENDING_KEY!r})")


def new_page(context: Any, base_url: str) -> Any:
    page = context.new_page()
    response = page.goto(base_url + "/", wait_until="load")
    if response is None or response.status != 200:
        raise CheckError(f"home returned {None if response is None else response.status}")
    input_locator(page)
    return page


def run(site_root: Path) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise CheckError("Playwright is required") from exc

    handler = partial(Quiet, directory=str(site_root.resolve(strict=True)))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    evidence: dict[str, Any] = {"base_url": base_url}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome")

            context = browser.new_context(service_workers="block")
            page = new_page(context, base_url)
            fill(page, "policy")
            first_href = pointer_activate_without_navigation(page)
            if history(page) != ["policy"]:
                raise CheckError(f"trusted pointer activation did not store policy: {history(page)!r}")
            fill(page, "composition")
            pointer_activate_without_navigation(page)
            if history(page) != ["composition", "policy"]:
                raise CheckError(f"trusted pointer activation did not preserve MRU: {history(page)!r}")

            pre_replay = result_signature(page)
            fill(page, "")
            wait_history_visible(page)
            page.evaluate(
                f"""() => {{
                  const root = {ROOT_EXPR};
                  window.__siteReplayRootEvents = [];
                  root?.addEventListener('input', (event) => {{
                    window.__siteReplayRootEvents.push({{
                      inputEvent: event instanceof InputEvent,
                      bubbles: event.bubbles,
                      value: event.target?.value || '',
                    }});
                  }});
                }}"""
            )
            page.locator('button[data-site-search-history-query="policy"]').click(timeout=5_000)
            page.wait_for_function(
                f"""() => {{
                  const root = {ROOT_EXPR};
                  return root?.querySelector('input[role=\"combobox\"]')?.value === 'policy';
                }}""",
                timeout=5_000,
            )
            page.wait_for_function(
                f"""(before) => {{
                  const root = {ROOT_EXPR};
                  const now = Array.from(root?.querySelectorAll('ol a[href]') || [])
                    .map((anchor) => `${{anchor.getAttribute('href')}}|${{anchor.textContent?.trim() || ''}}`);
                  return now.length > 0 && JSON.stringify(now) !== JSON.stringify(before);
                }}""",
                arg=pre_replay,
                timeout=10_000,
            )
            replay_events = page.evaluate("() => window.__siteReplayRootEvents || []")
            if not replay_events or not replay_events[-1]["inputEvent"] or not replay_events[-1]["bubbles"]:
                raise CheckError(f"replay event was not a bubbling InputEvent at ShadowRoot: {replay_events!r}")
            if history(page) != ["policy", "composition"]:
                raise CheckError(f"replay did not update MRU: {history(page)!r}")

            fill(page, "")
            wait_history_visible(page)
            page.evaluate(
                f"""() => {{
                  const root = {HISTORY_ROOT_EXPR};
                  window.__siteClearReachedRoot = 0;
                  root?.addEventListener('click', (event) => {{
                    if (event.composedPath().some((node) => node instanceof Element && node.matches?.('[data-site-search-history-clear]'))) {{
                      window.__siteClearReachedRoot += 1;
                    }}
                  }});
                }}"""
            )
            page.locator('button[data-site-search-history-clear]').click(timeout=5_000)
            if page.evaluate("() => window.__siteClearReachedRoot") != 0:
                raise CheckError("Clear click leaked to the ShadowRoot")
            if history(page):
                raise CheckError("Clear did not empty history")
            context.close()

            context = browser.new_context(service_workers="block")
            page = new_page(context, base_url)
            page.wait_for_function(
                f"""() => {{ const root = {HISTORY_ROOT_EXPR}; return Boolean(root); }}""",
                timeout=5_000,
            )
            prepared = page.evaluate(
                f"""() => {{
                  const root = {HISTORY_ROOT_EXPR};
                  const section = root?.querySelector('[data-site-search-history]');
                  const input = root?.querySelector('input[role=\"combobox\"]');
                  if (!(section instanceof HTMLElement) || !(input instanceof HTMLInputElement)) return false;
                  section.hidden = false;
                  input.remove();
                  return true;
                }}"""
            )
            if not prepared:
                raise CheckError("could not prepare disconnected-input regression")
            page.wait_for_function(
                f"""() => {{
                  const root = {HISTORY_ROOT_EXPR};
                  const section = root?.querySelector('[data-site-search-history]');
                  return Boolean(section && section.hidden);
                }}""",
                timeout=5_000,
            )
            context.close()

            context = browser.new_context(service_workers="block")
            page = new_page(context, base_url)
            fill(page, "policy")
            wait_results(page)
            install_write_counter(page)
            start_url = page.url
            page.evaluate(
                f"""() => {{
                  const root = {ROOT_EXPR};
                  const input = root?.querySelector('input[role=\"combobox\"]');
                  input?.addEventListener('keydown', (event) => {{
                    if (event.key === 'Enter') {{
                      event.preventDefault();
                      event.stopImmediatePropagation();
                    }}
                  }}, {{ capture: true, once: true }});
                }}"""
            )
            input_locator(page).press("Enter")
            page.wait_for_timeout(1250)
            if page.url != start_url:
                raise CheckError(f"cancelled Enter navigated unexpectedly: {page.url}")
            if history(page) or write_count(page) != 0:
                raise CheckError(
                    f"cancelled Enter recorded history: history={history(page)!r} writes={write_count(page)}"
                )
            context.close()

            context = browser.new_context(service_workers="block")
            page = new_page(context, base_url)
            fill(page, "policy")
            wait_results(page)
            result_urls = page.evaluate(
                f"""() => {{
                  const root = {ROOT_EXPR};
                  return Array.from(root?.querySelectorAll('ol a[href]') || []).map((anchor) => anchor.href);
                }}"""
            )
            if not result_urls:
                raise CheckError("normal Enter scenario has no result URLs")
            install_write_counter(page)
            search_input = input_locator(page)
            search_input.press("ArrowDown")
            with page.expect_navigation(wait_until="load", timeout=10_000):
                search_input.press("Enter")
            destination = clean_navigation_key(page.url)
            expected = {clean_navigation_key(url) for url in result_urls}
            if destination not in expected:
                raise CheckError(f"Enter navigated outside staged results: {page.url} not in {sorted(expected)!r}")
            if history(page) != ["policy"]:
                raise CheckError(f"normal Enter did not store policy after navigation: {history(page)!r}")
            if write_count(page) != 1:
                raise CheckError(f"normal Enter wrote history {write_count(page)} times, expected exactly once")
            normal_enter_url = page.url
            context.close()

            context = browser.new_context(service_workers="block")
            install_no_navigation_api(context)
            page = new_page(context, base_url)
            if page.evaluate("() => window.navigation !== undefined"):
                raise CheckError("could not disable Navigation API for fallback regression")
            fill(page, "policy")
            wait_results(page)
            page.evaluate(
                f"""() => {{
                  const root = {ROOT_EXPR};
                  const input = root?.querySelector('input[role=\"combobox\"]');
                  input?.addEventListener('keydown', (event) => {{
                    if (event.key === 'Enter') {{
                      event.preventDefault();
                      event.stopImmediatePropagation();
                    }}
                  }}, {{ capture: true, once: true }});
                }}"""
            )
            input_locator(page).press("Enter")
            response = page.goto(base_url + "/?site-search-history-mismatch=1", wait_until="load")
            if response is None or response.status != 200:
                raise CheckError("fallback mismatch navigation did not load")
            if pending_write_count(page) != 1:
                raise CheckError(
                    f"fallback mismatch did not exercise one pagehide handoff: {pending_write_count(page)}"
                )
            if history(page) or write_count(page) != 0:
                raise CheckError(
                    f"fallback mismatched destination recorded history: history={history(page)!r} writes={write_count(page)}"
                )
            if pending_record(page) is not None:
                raise CheckError(f"fallback mismatched destination left pending state: {pending_record(page)!r}")
            context.close()

            context = browser.new_context(service_workers="block")
            install_no_navigation_api(context)
            page = new_page(context, base_url)
            fill(page, "policy")
            wait_results(page)
            page.evaluate(
                f"""() => {{
                  const root = {ROOT_EXPR};
                  const input = root?.querySelector('input[role=\"combobox\"]');
                  input?.addEventListener('keydown', (event) => {{
                    if (event.key === 'Enter') {{
                      event.preventDefault();
                      event.stopImmediatePropagation();
                    }}
                  }}, {{ capture: true, once: true }});
                }}"""
            )
            input_locator(page).press("Enter")
            staged_at = page.evaluate("() => Date.now()")
            expiry_wait_ms = 1250
            page.wait_for_timeout(expiry_wait_ms)
            pagehide_at = page.evaluate(
                """() => {
                  window.dispatchEvent(new PageTransitionEvent('pagehide'));
                  return Date.now();
                }"""
            )
            raw_expiry_pending = pending_record(page)
            if raw_expiry_pending is None:
                raise CheckError("fallback pagehide did not persist pending state for expiry check")
            try:
                expiry_pending = json.loads(raw_expiry_pending)
            except json.JSONDecodeError as exc:
                raise CheckError(f"fallback pagehide persisted invalid pending JSON: {raw_expiry_pending!r}") from exc
            expiry_value = expiry_pending.get("expiresAt")
            if not isinstance(expiry_value, (int, float)):
                raise CheckError(f"fallback pagehide pending expiry is invalid: {expiry_pending!r}")
            expiry_remaining_ms = int(expiry_value - pagehide_at)
            if expiry_remaining_ms <= 0:
                raise CheckError(f"fallback pagehide pending expiry was already stale: {expiry_remaining_ms}")
            if expiry_value > staged_at + 15_250:
                raise CheckError(
                    "fallback pagehide extended pending expiry instead of preserving the original deadline: "
                    f"staged_at={staged_at} expires_at={expiry_value} pagehide_at={pagehide_at}"
                )
            if pending_write_count(page) != 1:
                raise CheckError(
                    f"fallback expiry check expected one pagehide handoff, got {pending_write_count(page)}"
                )
            if history(page) or write_count(page) != 0:
                raise CheckError(
                    f"fallback expiry handoff recorded history unexpectedly: history={history(page)!r} writes={write_count(page)}"
                )
            context.close()

            context = browser.new_context(service_workers="block")
            install_no_navigation_api(context)
            page = new_page(context, base_url)
            fill(page, "policy")
            wait_results(page)
            delayed_result_urls = page.evaluate(
                f"""() => {{
                  const root = {ROOT_EXPR};
                  return Array.from(root?.querySelectorAll('ol a[href]') || []).map((anchor) => anchor.href);
                }}"""
            )
            if not delayed_result_urls:
                raise CheckError("delayed fallback same-document scenario has no result URLs")
            page.evaluate(
                f"""() => {{
                  const root = {ROOT_EXPR};
                  const input = root?.querySelector('input[role=\"combobox\"]');
                  input?.addEventListener('keydown', (event) => {{
                    if (event.key === 'Enter') {{
                      event.preventDefault();
                      event.stopImmediatePropagation();
                    }}
                  }}, {{ capture: true, once: true }});
                }}"""
            )
            input_locator(page).press("Enter")
            delayed_wait_ms = 1250
            page.wait_for_timeout(delayed_wait_ms)
            delayed_target = delayed_result_urls[0]
            page.evaluate(
                """(destination) => {
                  history.pushState({}, '', destination);
                  window.dispatchEvent(new PopStateEvent('popstate'));
                }""",
                delayed_target,
            )
            page.wait_for_function(
                f"() => JSON.parse(localStorage.getItem({KEY!r}) || '[]')[0] === 'policy'",
                timeout=5_000,
            )
            if history(page) != ["policy"]:
                raise CheckError(
                    f"delayed fallback same-document signal did not store policy: {history(page)!r}"
                )
            if write_count(page) != 1:
                raise CheckError(
                    f"delayed fallback same-document signal wrote history {write_count(page)} times, expected once"
                )
            if pending_write_count(page) != 0:
                raise CheckError(
                    f"delayed fallback same-document signal unexpectedly used pagehide handoff: {pending_write_count(page)}"
                )
            if pending_record(page) is not None:
                raise CheckError(
                    f"delayed fallback same-document signal left session pending state: {pending_record(page)!r}"
                )
            delayed_fallback_url = page.url
            delayed_fallback_writes = write_count(page)
            context.close()

            context = browser.new_context(service_workers="block")
            install_no_navigation_api(context)
            page = new_page(context, base_url)
            fill(page, "policy")
            wait_results(page)
            fallback_result_urls = page.evaluate(
                f"""() => {{
                  const root = {ROOT_EXPR};
                  return Array.from(root?.querySelectorAll('ol a[href]') || []).map((anchor) => anchor.href);
                }}"""
            )
            if not fallback_result_urls:
                raise CheckError("fallback Enter scenario has no result URLs")
            search_input = input_locator(page)
            search_input.press("ArrowDown")
            with page.expect_navigation(wait_until="load", timeout=10_000):
                search_input.press("Enter")
            fallback_destination = clean_navigation_key(page.url)
            fallback_expected = {clean_navigation_key(url) for url in fallback_result_urls}
            if fallback_destination not in fallback_expected:
                raise CheckError(
                    f"fallback Enter navigated outside staged results: {page.url} not in {sorted(fallback_expected)!r}"
                )
            if pending_write_count(page) != 1:
                raise CheckError(
                    f"fallback Enter did not exercise one pagehide handoff: {pending_write_count(page)}"
                )
            if history(page) != ["policy"]:
                raise CheckError(f"fallback Enter did not store policy after confirmed navigation: {history(page)!r}")
            if write_count(page) != 1:
                raise CheckError(
                    f"fallback Enter wrote history {write_count(page)} times, expected exactly once"
                )
            if pending_record(page) is not None:
                raise CheckError(f"fallback Enter left pending state after confirmation: {pending_record(page)!r}")
            fallback_enter_url = page.url

            evidence.update(
                {
                    "pointer_result_href": first_href,
                    "replay_result_changed": True,
                    "replay_bubbling_input_event": True,
                    "clear_isolated_from_shadow_root": True,
                    "disconnected_input_hides_history": True,
                    "cancelled_enter_not_recorded": True,
                    "enter_navigation_url": normal_enter_url,
                    "enter_history_writes": 1,
                    "fallback_navigation_api_disabled": True,
                    "fallback_pagehide_handoffs": pending_write_count(page),
                    "fallback_mismatch_not_recorded": True,
                    "fallback_pagehide_expiry_wait_ms": expiry_wait_ms,
                    "fallback_pagehide_expiry_remaining_ms": expiry_remaining_ms,
                    "fallback_pagehide_expiry_preserved": True,
                    "fallback_delayed_same_document_wait_ms": delayed_wait_ms,
                    "fallback_delayed_same_document_navigation_url": delayed_fallback_url,
                    "fallback_delayed_same_document_history_writes": delayed_fallback_writes,
                    "fallback_delayed_same_document_no_pagehide_handoff": True,
                    "fallback_enter_navigation_url": fallback_enter_url,
                    "fallback_enter_history_writes": write_count(page),
                    "fallback_pending_cleared": True,
                }
            )
            context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evidence = run(args.site_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())