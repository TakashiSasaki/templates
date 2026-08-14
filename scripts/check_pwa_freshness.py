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


class PwaFreshnessError(RuntimeError):
    """Raised when the browser does not satisfy the PWA freshness contract."""


@dataclass
class FixtureState:
    document_version: int = 1
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

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send(
            self,
            body: bytes,
            content_type: str,
            *,
            cache_control: str = "no-store",
            etag: str | None = None,
        ) -> None:
            if etag and self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("Cache-Control", cache_control)
                self.send_header("ETag", etag)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", cache_control)
            if etag:
                self.send_header("ETag", etag)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlsplit(self.path).path

            if path == "/":
                body = b"""<!doctype html>
<html>
<head><meta charset=\"utf-8\"><title>PWA freshness fixture</title></head>
<body><main id=\"fixture\">fixture</main><script src=\"/javascripts/pwa.js\"></script></body>
</html>
"""
                self._send(body, "text/html; charset=utf-8")
                return

            if path == "/javascripts/pwa.js":
                self._send(
                    registration_source,
                    "text/javascript; charset=utf-8",
                    cache_control="no-store",
                )
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
                body = f"document-v{state.document_version}\n".encode("utf-8")
                self._send(
                    body,
                    "text/html; charset=utf-8",
                    cache_control="public, max-age=3600",
                    etag=f'"document-v{state.document_version}"',
                )
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
            if _worker_version(page) == expected:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.1)
    message = f"service worker did not activate fixture version {expected}"
    if last_error is not None:
        raise PwaFreshnessError(message) from last_error
    raise PwaFreshnessError(message)


def _fetch_text(page: Any, path: str) -> str:
    return page.evaluate(
        "async (path) => { const response = await fetch(path); return await response.text(); }",
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


def run_check(site_root: Path, output: Path | None) -> dict[str, Any]:
    required = (
        site_root / "service-worker.js",
        site_root / "javascripts/pwa.js",
        site_root / "icon.svg",
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

            first_document = _fetch_text(page, "/document/")
            if first_document.strip() != "document-v1":
                raise PwaFreshnessError(
                    f"initial document mismatch: {first_document!r}"
                )
            state.document_version = 2
            second_document = _fetch_text(page, "/document/")
            if second_document.strip() != "document-v2":
                raise PwaFreshnessError(
                    "document request reused stale HTTP cache instead of revalidating"
                )
            evidence["document_versions"] = [
                first_document.strip(),
                second_document.strip(),
            ]

            initial_manifest = _fetch_manifest_version(page)
            if initial_manifest != 1:
                raise PwaFreshnessError(
                    f"initial cached manifest version is {initial_manifest}, expected 1"
                )
            state.manifest_version = 2
            observed_manifest_versions: list[int] = []
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                version = _fetch_manifest_version(page)
                observed_manifest_versions.append(version)
                if version == 2:
                    break
                time.sleep(0.1)
            else:
                raise PwaFreshnessError(
                    "cached manifest did not converge to the revalidated network version"
                )
            evidence["manifest_versions"] = [initial_manifest, *observed_manifest_versions]

            state.worker_version = 2
            page.reload(wait_until="load")
            _wait_for_worker_version(page, 2)
            evidence["worker_version"] = 2

            context.set_offline(True)
            offline_fetch = page.evaluate(
                """async () => {
                  const response = await fetch("/document/");
                  return { status: response.status, body: await response.text() };
                }"""
            )
            if offline_fetch.get("status") != 503 or "unavailable while offline" not in offline_fetch.get("body", ""):
                raise PwaFreshnessError(
                    "offline instant-navigation document fetch did not return the explicit 503 fallback"
                )
            evidence["offline_fetch_status"] = 503

            response = page.goto(base_url + "/document/", wait_until="load")
            if response is None or response.status != 503:
                status = None if response is None else response.status
                raise PwaFreshnessError(
                    f"offline document navigation returned {status}, expected 503"
                )
            offline_body = page.locator("body").inner_text()
            if "unavailable while offline" not in offline_body:
                raise PwaFreshnessError(
                    "offline navigation did not return the explicit Service Worker fallback"
                )
            evidence["offline_status"] = 503
            context.set_offline(False)

            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

    hits = state.snapshot_hits()
    evidence["hits"] = hits
    if hits["document"] < 2:
        raise PwaFreshnessError("document revalidation did not reach the fixture server")
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
