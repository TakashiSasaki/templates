#!/usr/bin/env python3
"""Exercise PWA document-cache and commit-correlation regressions in Chromium."""

from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


DOCUMENT_CACHE_NAME = "templates-portal-documents-v1"
DOCUMENT_OBSERVABLE_FIXTURE = """<script>
globalThis.__pwaDocumentSubscribers = [];
globalThis.document$ = {
  subscribe(callback) {
    globalThis.__pwaDocumentSubscribers.push(callback);
  },
};
globalThis.__pwaFixtureCommitDocument = (url) => {
  history.pushState({}, "", url);
  for (const callback of globalThis.__pwaDocumentSubscribers) {
    callback({ body: document.body });
  }
};
</script>"""


class PwaCommitRegressionError(RuntimeError):
    """Raised when a document-cache or commit-correlation invariant is violated."""


@dataclass
class FixtureState:
    document_version: int = 1
    race_mode: bool = False
    race_request_count: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def begin_race(self) -> None:
        with self.lock:
            self.race_mode = True
            self.race_request_count = 0

    def next_race_request(self) -> tuple[bool, int]:
        with self.lock:
            self.race_request_count += 1
            return self.race_mode, self.race_request_count


def _fixture_handler(site_root: Path, state: FixtureState) -> type[BaseHTTPRequestHandler]:
    worker_source = (site_root / "service-worker.js").read_text(encoding="utf-8")
    registration_source = (site_root / "javascripts/pwa.js").read_bytes()
    resolved_site_root = site_root.resolve()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send(
            self,
            body: bytes,
            content_type: str,
            *,
            status: int = 200,
            cache_control: str = "no-store",
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", cache_control)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _send_static(self, path: str) -> bool:
            candidate = (resolved_site_root / path.lstrip("/")).resolve()
            try:
                candidate.relative_to(resolved_site_root)
            except ValueError:
                return False
            if not candidate.is_file():
                return False
            content_types = {
                ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".json": "application/json; charset=utf-8",
                ".svg": "image/svg+xml",
                ".png": "image/png",
                ".woff": "font/woff",
                ".woff2": "font/woff2",
            }
            self._send(
                candidate.read_bytes(),
                content_types.get(candidate.suffix.lower(), "application/octet-stream"),
            )
            return True

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/":
                body = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><link rel="stylesheet" href="/stylesheets/freshness-status.css"><title>Commit fixture</title></head>
<body><main>shell</main>{DOCUMENT_OBSERVABLE_FIXTURE}<script src="/javascripts/pwa.js"></script></body>
</html>
""".encode("utf-8")
                self._send(body, "text/html; charset=utf-8")
                return

            if path == "/service-worker.js":
                self._send(
                    worker_source.encode("utf-8"),
                    "text/javascript; charset=utf-8",
                    cache_control="no-cache",
                )
                return

            if path == "/javascripts/pwa.js":
                self._send(registration_source, "text/javascript; charset=utf-8")
                return

            if path in {"/document", "/document/", "/document/index.html"}:
                body = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Document fixture</title></head>
<body><main>document-v{state.document_version}</main>{DOCUMENT_OBSERVABLE_FIXTURE}<script src="/javascripts/pwa.js"></script></body>
</html>
""".encode("utf-8")
                self._send(body, "text/html; charset=utf-8")
                return

            if path in {"/race", "/race/", "/race/index.html"}:
                race_mode, request_number = state.next_race_request()
                if not race_mode:
                    body = b"<!doctype html><html><head><title>Race seed</title></head><body><main>race-seed</main></body></html>"
                    self._send(body, "text/html; charset=utf-8")
                    return
                if request_number == 1:
                    time.sleep(0.35)
                    body = b"<!doctype html><html><head><title>Old race response</title></head><body><main>race-old-200</main></body></html>"
                    self._send(body, "text/html; charset=utf-8")
                    return
                self._send(b"", "text/plain; charset=utf-8", status=404)
                return

            if self._send_static(path):
                return

            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    return Handler


def _fetch_document(page: Any) -> dict[str, Any]:
    return _fetch_path(page, "/document/")


def _fetch_path(page: Any, path: str) -> dict[str, Any]:
    return page.evaluate(
        """async (path) => {
          const response = await fetch(path);
          return {
            status: response.status,
            body: await response.text(),
            freshness: response.headers.get('X-Templates-Freshness'),
          };
        }""",
        path,
    )


def _cached_body(page: Any, path: str) -> str | None:
    return page.evaluate(
        """async ([cacheName, path]) => {
          const cache = await caches.open(cacheName);
          const response = await cache.match(path);
          return response ? await response.text() : null;
        }""",
        [DOCUMENT_CACHE_NAME, path],
    )


def _wait_for_cached_text(
    page: Any,
    path: str,
    expected: str,
    timeout_seconds: float = 5.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        body = _cached_body(page, path)
        if body is not None and expected in body:
            return
        time.sleep(0.05)
    raise PwaCommitRegressionError(
        f"document cache for {path} did not converge to content containing {expected!r}"
    )


def run_check(site_root: Path, output: Path | None) -> dict[str, Any]:
    required = (
        site_root / "service-worker.js",
        site_root / "javascripts/pwa.js",
        site_root / "stylesheets/freshness-status.css",
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise PwaCommitRegressionError(
            "built site is missing required PWA commit-regression assets: "
            + ", ".join(path.as_posix() for path in missing)
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PwaCommitRegressionError("Playwright is required for PWA commit regression checks") from exc

    state = FixtureState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _fixture_handler(site_root, state))
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    evidence: dict[str, Any] = {"base_url": base_url}

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome")
            context = browser.new_context(service_workers="allow")
            page = context.new_page()
            page.goto(base_url + "/", wait_until="load")
            page.evaluate("() => navigator.serviceWorker.ready.then(() => undefined)")
            page.wait_for_function("() => navigator.serviceWorker.controller !== null")

            initial = _fetch_document(page)
            if initial["status"] != 200 or "document-v1" not in initial["body"]:
                raise PwaCommitRegressionError(f"initial document mismatch: {initial!r}")
            _wait_for_cached_text(page, "/document/", "document-v1")

            uncached_missing = _fetch_path(page, "/uncached-404/")
            if uncached_missing["status"] != 404:
                raise PwaCommitRegressionError(
                    f"uncached authoritative miss returned {uncached_missing['status']}, expected 404"
                )
            _wait_for_cached_text(page, "/document/", "document-v1")
            evidence["uncached_404_preserved_other_documents"] = True

            context.set_offline(True)
            cached = _fetch_document(page)
            if (
                cached["status"] != 200
                or cached["freshness"] != "cached-unverified"
                or "document-v1" not in cached["body"]
            ):
                raise PwaCommitRegressionError(f"cached fallback mismatch: {cached!r}")
            page.wait_for_selector("#templates-freshness-status")

            context.set_offline(False)
            state.document_version = 2
            fresh_retry = _fetch_document(page)
            if fresh_retry["status"] != 200 or "document-v2" not in fresh_retry["body"]:
                raise PwaCommitRegressionError(f"fresh retry mismatch: {fresh_retry!r}")
            if page.locator("#templates-freshness-status").count() != 1:
                raise PwaCommitRegressionError("fresh retry cleared the stale warning before commit")
            page.evaluate("() => globalThis.__pwaFixtureCommitDocument('/document/')")
            page.wait_for_selector("#templates-freshness-status", state="detached")
            evidence["same_url_fresh_retry_cleared_on_commit"] = True
            _wait_for_cached_text(page, "/document/", "document-v2")

            context.set_offline(True)
            response = page.goto(base_url + "/document/", wait_until="load")
            if response is None or response.status != 200:
                status = None if response is None else response.status
                raise PwaCommitRegressionError(
                    f"offline full navigation returned {status}, expected 200"
                )
            if "document-v2" not in page.locator("body").inner_text():
                raise PwaCommitRegressionError("offline full navigation did not render cached v2")
            if page.locator("#templates-freshness-status").count() != 1:
                raise PwaCommitRegressionError("offline full navigation omitted stale warning")
            if page.locator("html").get_attribute("data-templates-cached-fallback") != "true":
                raise PwaCommitRegressionError("cached full-navigation marker was not present")

            page.evaluate("() => globalThis.__pwaFixtureCommitDocument('/document/')")
            if page.locator("#templates-freshness-status").count() != 1:
                raise PwaCommitRegressionError("initial full-navigation document commit cleared stale warning")
            if page.locator("html").get_attribute("data-templates-cached-fallback") is not None:
                raise PwaCommitRegressionError("cached full-navigation marker was not consumed")
            position = page.locator("#templates-freshness-status").evaluate(
                "element => getComputedStyle(element).position"
            )
            if position != "fixed":
                raise PwaCommitRegressionError(
                    f"standalone cached warning was not fixed in the viewport: {position!r}"
                )
            evidence["full_navigation_commit_retained_warning"] = True
            evidence["standalone_inline_warning_style"] = True

            page.evaluate("() => globalThis.__pwaFixtureCommitDocument('/document/#heading')")
            if page.locator("#templates-freshness-status").count() != 1:
                raise PwaCommitRegressionError(
                    "in-page anchor document event cleared the cached-unverified warning"
                )
            evidence["anchor_event_retained_cached_warning"] = True

            context.set_offline(False)
            seed = _fetch_path(page, "/race/")
            if seed["status"] != 200 or "race-seed" not in seed["body"]:
                raise PwaCommitRegressionError(f"race seed mismatch: {seed!r}")
            _wait_for_cached_text(page, "/race/", "race-seed")
            state.begin_race()
            race_results = page.evaluate(
                """async () => {
                  const first = fetch('/race/').then(async (response) => ({
                    status: response.status,
                    body: await response.text(),
                  }));
                  await new Promise((resolve) => setTimeout(resolve, 50));
                  const second = fetch('/race/').then(async (response) => ({
                    status: response.status,
                    body: await response.text(),
                  }));
                  return await Promise.all([first, second]);
                }"""
            )
            if [result["status"] for result in race_results] != [200, 404]:
                raise PwaCommitRegressionError(
                    f"authoritative deletion race did not produce delayed 200 then newer 404: {race_results!r}"
                )
            time.sleep(0.3)
            if _cached_body(page, "/race/") is not None:
                raise PwaCommitRegressionError(
                    "older delayed 200 resurrected a document after a newer authoritative 404"
                )
            evidence["older_200_did_not_resurrect_after_newer_404"] = True
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evidence = run_check(args.site_root.resolve(), args.output)
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
