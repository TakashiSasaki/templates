#!/usr/bin/env python3
"""Exercise PWA freshness invariants in a real Chromium service-worker context."""

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


class PwaFreshnessError(RuntimeError):
    """Raised when the browser does not satisfy the PWA freshness contract."""


@dataclass
class FixtureState:
    document_version: int = 1
    document_status: int = 200
    manifest_version: int = 1
    worker_version: int = 1
    hits: dict[str, int] = field(
        default_factory=lambda: {"document": 0, "manifest": 0, "worker": 0}
    )
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_hit(self, asset: str) -> None:
        with self.lock:
            self.hits[asset] += 1

    def snapshot_hits(self) -> dict[str, int]:
        with self.lock:
            return dict(self.hits)


def _fixture_handler(site_root: Path, state: FixtureState) -> type[BaseHTTPRequestHandler]:
    worker_source = (site_root / "service-worker.js").read_text(encoding="utf-8")
    registration_source = (site_root / "javascripts/pwa.js").read_bytes()
    icon_source = (site_root / "icon.svg").read_bytes()
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
            etag: str | None = None,
        ) -> None:
            if status == 200 and etag and self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("Cache-Control", cache_control)
                self.send_header("ETag", etag)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", cache_control)
            if etag and status == 200:
                self.send_header("ETag", etag)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_static_fixture_asset(self, path: str) -> bool:
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
<head><meta charset="utf-8"><title>PWA freshness fixture</title><link rel="stylesheet" href="/stylesheets/freshness-status.css"></head>
<body><main id="fixture">fixture</main>{DOCUMENT_OBSERVABLE_FIXTURE}<script src="/javascripts/pwa.js"></script></body>
</html>
""".encode("utf-8")
                self._send(body, "text/html; charset=utf-8")
                return

            if path == "/legacy/":
                body = b"""<!doctype html>
<html>
<head><meta charset=\"utf-8\"><title>Legacy client fixture</title></head>
<body><main id=\"legacy\">legacy-client-without-freshness-ui</main></body>
</html>
"""
                self._send(body, "text/html; charset=utf-8")
                return

            if path == "/javascripts/pwa.js":
                self._send(registration_source, "text/javascript; charset=utf-8")
                return

            if path == "/service-worker.js":
                state.record_hit("worker")
                marker = f"""const __PWA_FIXTURE_WORKER_VERSION = {state.worker_version};
self.addEventListener("message", (event) => {{
  if (event.data === "__pwa_fixture_worker_version__" && event.source) {{
    event.source.postMessage({{
      type: "__pwa_fixture_worker_version__",
      version: __PWA_FIXTURE_WORKER_VERSION,
    }});
  }}
}});
"""
                body = (worker_source + "\n" + marker).encode("utf-8")
                self._send(
                    body,
                    "text/javascript; charset=utf-8",
                    cache_control="public, max-age=3600",
                    etag=f'"worker-v{state.worker_version}"',
                )
                return

            if path == "/app.webmanifest":
                state.record_hit("manifest")
                body = json.dumps(
                    {
                        "name": "PWA freshness fixture",
                        "short_name": "fixture",
                        "start_url": "/",
                        "scope": "/",
                        "display": "standalone",
                        "icons": [],
                        "fixture_version": state.manifest_version,
                    },
                    separators=(",", ":"),
                ).encode("utf-8")
                self._send(
                    body,
                    "application/manifest+json; charset=utf-8",
                    cache_control="public, max-age=3600",
                    etag=f'"manifest-v{state.manifest_version}"',
                )
                return

            if path == "/icon.svg":
                self._send(
                    icon_source,
                    "image/svg+xml",
                    cache_control="public, max-age=3600",
                    etag='"icon-v1"',
                )
                return

            if path in {"/document", "/document/", "/document/index.html"}:
                state.record_hit("document")
                body = (
                    "<!doctype html><html><head><meta charset=\"utf-8\">"
                    '<link rel="stylesheet" href="/stylesheets/freshness-status.css">'
                    "<title>Document fixture</title></head><body>"
                    f"<main>document-v{state.document_version}</main>"
                    '<script src="/javascripts/pwa.js"></script>'
                    "</body></html>"
                ).encode("utf-8")
                self._send(
                    body,
                    "text/html; charset=utf-8",
                    status=state.document_status,
                    cache_control="public, max-age=3600",
                    etag=f'"document-v{state.document_version}"',
                )
                return

            if self._send_static_fixture_asset(path):
                return

            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    return Handler


def _worker_version(page: Any) -> int | None:
    return page.evaluate(
        """async () => {
          const worker = navigator.serviceWorker.controller;
          if (!worker) return null;
          navigator.serviceWorker.startMessages();
          return await new Promise((resolve) => {
            const timer = setTimeout(() => {
              navigator.serviceWorker.removeEventListener("message", onMessage);
              resolve(null);
            }, 1000);
            const onMessage = (event) => {
              if (event.data?.type === "__pwa_fixture_worker_version__") {
                clearTimeout(timer);
                navigator.serviceWorker.removeEventListener("message", onMessage);
                resolve(event.data.version);
              }
            };
            navigator.serviceWorker.addEventListener("message", onMessage);
            worker.postMessage("__pwa_fixture_worker_version__");
          });
        }"""
    )


def _wait_for_worker_version(page: Any, expected: int, timeout_seconds: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            version = _worker_version(page)
            last_error = None
            if version == expected:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.1)
    message = f"service worker did not activate fixture version {expected}"
    if last_error is not None:
        raise PwaFreshnessError(message) from last_error
    raise PwaFreshnessError(message)


def _request_worker_update(page: Any) -> None:
    page.evaluate(
        """async () => {
          const registration = await navigator.serviceWorker.getRegistration("/");
          if (!registration) {
            throw new Error("service worker registration unavailable");
          }
          await registration.update();
        }"""
    )


def _fetch_response(page: Any, path: str) -> dict[str, Any]:
    return page.evaluate(
        """async (path) => {
          const response = await fetch(path);
          return {
            status: response.status,
            body: await response.text(),
            freshness: response.headers.get("X-Templates-Freshness"),
          };
        }""",
        path,
    )


def _fetch_manifest_version(page: Any) -> int:
    return int(
        page.evaluate(
            """async () => {
              const response = await fetch("/app.webmanifest");
              const manifest = await response.json();
              return manifest.fixture_version;
            }"""
        )
    )


def _wait_for_manifest_version(page: Any, expected: int, timeout_seconds: float = 10.0) -> list[int]:
    deadline = time.monotonic() + timeout_seconds
    observed_versions: list[int] = []
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            version = _fetch_manifest_version(page)
            last_error = None
            observed_versions.append(version)
            if version == expected:
                return observed_versions
        except Exception as exc:
            last_error = exc
        time.sleep(0.1)
    message = f"cached manifest did not converge to fixture version {expected}"
    if last_error is not None:
        raise PwaFreshnessError(message) from last_error
    raise PwaFreshnessError(message)


def _document_is_cached(page: Any, path: str) -> bool:
    return bool(
        page.evaluate(
            """async ([cacheName, path]) => {
              const cache = await caches.open(cacheName);
              return Boolean(await cache.match(path));
            }""",
            [DOCUMENT_CACHE_NAME, path],
        )
    )


def _wait_for_document_cache(page: Any, path: str, expected: bool, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            cached = _document_is_cached(page, path)
            last_error = None
            if cached is expected:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.05)
    message = f"document cache state for {path} did not become {expected}"
    if last_error is not None:
        raise PwaFreshnessError(message) from last_error
    raise PwaFreshnessError(message)


def _commit_fixture_document(page: Any, path: str) -> None:
    page.evaluate("path => globalThis.__pwaFixtureCommitDocument(path)", path)


def run_check(site_root: Path, output: Path | None) -> dict[str, Any]:
    required = (
        site_root / "service-worker.js",
        site_root / "javascripts/pwa.js",
        site_root / "icon.svg",
        site_root / "app.webmanifest",
        site_root / "stylesheets/freshness-status.css",
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise PwaFreshnessError(
            "built site is missing required PWA assets: "
            + ", ".join(path.as_posix() for path in missing)
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PwaFreshnessError("Playwright is required for PWA freshness checks") from exc

    state = FixtureState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _fixture_handler(site_root, state))
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    evidence: dict[str, Any] = {"base_url": base_url}

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(service_workers="allow")
            page = context.new_page()
            page.goto(base_url + "/", wait_until="load")
            page.evaluate("() => navigator.serviceWorker.ready.then(() => undefined)")
            page.wait_for_function("() => navigator.serviceWorker.controller !== null")
            _wait_for_worker_version(page, 1)

            first_document = _fetch_response(page, "/document/")
            if first_document["status"] != 200 or "document-v1" not in first_document["body"]:
                raise PwaFreshnessError(f"initial document mismatch: {first_document!r}")
            state.document_version = 2
            second_document = _fetch_response(page, "/document/")
            if second_document["status"] != 200 or "document-v2" not in second_document["body"]:
                raise PwaFreshnessError("document request reused stale HTTP cache instead of revalidating")
            if second_document["freshness"] is not None:
                raise PwaFreshnessError("network document was incorrectly marked as cached")
            _wait_for_document_cache(page, "/document/", True)
            evidence["document_versions"] = ["document-v1", "document-v2"]

            initial_manifest = _fetch_manifest_version(page)
            if initial_manifest != 1:
                raise PwaFreshnessError(f"initial cached manifest version is {initial_manifest}, expected 1")
            state.manifest_version = 2
            evidence["manifest_versions"] = [initial_manifest, *_wait_for_manifest_version(page, 2)]

            state.worker_version = 2
            _request_worker_update(page)
            _wait_for_worker_version(page, 2)
            page.reload(wait_until="load")
            _wait_for_worker_version(page, 2)
            _wait_for_document_cache(page, "/document/", True)
            evidence["worker_version"] = 2
            evidence["document_cache_survived_worker_update"] = True

            legacy_page = context.new_page()
            legacy_page.goto(base_url + "/legacy/", wait_until="load")
            legacy_page.wait_for_function("() => navigator.serviceWorker.controller !== null")
            context.set_offline(True)
            legacy_fallback = _fetch_response(legacy_page, "/document/")
            if legacy_fallback["status"] != 503:
                raise PwaFreshnessError("instant-navigation client without stale UI acknowledgement received cached HTML")
            evidence["legacy_instant_navigation_status"] = 503
            context.set_offline(False)
            legacy_page.close()

            context.set_offline(True)
            offline_cached = _fetch_response(page, "/document/")
            if (
                offline_cached["status"] != 200
                or offline_cached["freshness"] != "cached-unverified"
                or "document-v2" not in offline_cached["body"]
                or "Saved copy." not in offline_cached["body"]
            ):
                raise PwaFreshnessError(f"offline cached document was not explicitly marked stale: {offline_cached!r}")
            page.wait_for_selector("#templates-freshness-status")
            if "Saved copy." not in page.locator("#templates-freshness-status").inner_text():
                raise PwaFreshnessError("instant-navigation fallback did not expose the persistent stale warning")
            position = page.locator("#templates-freshness-status").evaluate("element => getComputedStyle(element).position")
            if position != "fixed":
                raise PwaFreshnessError(f"stale warning was not fixed in the viewport: {position!r}")
            evidence["offline_cached_status"] = 200
            evidence["instant_navigation_indicator"] = True

            _commit_fixture_document(page, "/document/")
            if page.locator("#templates-freshness-status").count() != 1:
                raise PwaFreshnessError("committing the cached fallback cleared its stale warning")
            evidence["stale_commit_retained_indicator"] = True

            context.set_offline(False)
            state.document_status = 403
            forbidden = _fetch_response(page, "/document/")
            if forbidden["status"] != 403 or forbidden["freshness"] is not None:
                raise PwaFreshnessError("ordinary 4xx response incorrectly fell back to cached documentation")
            if page.locator("#templates-freshness-status").count() != 1:
                raise PwaFreshnessError("uncommitted ordinary 4xx response cleared the stale warning")
            evidence["ordinary_4xx_status"] = 403

            state.document_status = 200
            verified = _fetch_response(page, "/document/")
            if verified["status"] != 200 or "document-v2" not in verified["body"]:
                raise PwaFreshnessError("verified network document did not reach the client")
            if page.locator("#templates-freshness-status").count() != 1:
                raise PwaFreshnessError("network fetch cleared stale warning before document commit")
            evidence["network_fetch_preserved_indicator_until_commit"] = True

            _commit_fixture_document(page, "/document/")
            page.wait_for_selector("#templates-freshness-status", state="detached")
            evidence["committed_navigation_cleared_indicator"] = True

            context.set_offline(True)
            response = page.goto(base_url + "/document/", wait_until="load")
            if response is None or response.status != 200:
                status = None if response is None else response.status
                raise PwaFreshnessError(f"offline cached document navigation returned {status}, expected 200")
            offline_body = page.locator("body").inner_text()
            if "Saved copy." not in offline_body or "document-v2" not in offline_body:
                raise PwaFreshnessError("offline navigation omitted cached-document freshness warning")
            if page.locator("#templates-freshness-status").count() != 1:
                raise PwaFreshnessError("offline full navigation did not render exactly one stale warning")
            evidence["offline_navigation_status"] = 200

            offline_miss = _fetch_response(page, "/uncached/")
            if offline_miss["status"] != 503 or "unavailable while offline" not in offline_miss["body"]:
                raise PwaFreshnessError(f"offline cache miss did not retain the explicit 503 fallback: {offline_miss!r}")
            evidence["offline_cache_miss_status"] = 503
            context.set_offline(False)

            state.document_status = 503
            server_error = _fetch_response(page, "/document/")
            if (
                server_error["status"] != 200
                or server_error["freshness"] != "cached-unverified"
                or "document-v2" not in server_error["body"]
            ):
                raise PwaFreshnessError("transient 5xx response did not fall back to the verified cached document")
            evidence["server_error_cached_status"] = 200

            state.document_status = 404
            deleted = _fetch_response(page, "/document/")
            if deleted["status"] != 404 or deleted["freshness"] is not None:
                raise PwaFreshnessError("authoritative deletion incorrectly returned cached documentation")
            _wait_for_document_cache(page, "/document/", False)
            evidence["authoritative_deletion_status"] = 404

            context.set_offline(True)
            deleted_offline = _fetch_response(page, "/document/")
            if deleted_offline["status"] != 503:
                raise PwaFreshnessError("deleted document remained available from cache after authoritative 404")
            evidence["deleted_document_offline_status"] = 503
            context.set_offline(False)
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

    hits = state.snapshot_hits()
    evidence["hits"] = hits
    if hits["document"] < 5:
        raise PwaFreshnessError("document lifecycle did not reach the fixture server")
    if hits["manifest"] < 2:
        raise PwaFreshnessError("manifest revalidation did not reach the fixture server")
    if hits["worker"] < 2:
        raise PwaFreshnessError("service worker update did not refetch the worker script")

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
