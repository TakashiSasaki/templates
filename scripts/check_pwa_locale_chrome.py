#!/usr/bin/env python3
"""Exercise localized PWA freshness chrome in a real Chromium context."""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


DOCUMENT_CACHE_NAME = "templates-portal-documents-v1"
TEST_MESSAGE_TYPE = "__templates_test_emit_update_available__"
EXPECTED_JA = {
    "saved_copy": "保存済みのコピーです。",
    "unverified": "最新版であることを確認できませんでした。",
    "update_available": "更新があります。",
    "published_changed": "公開済みページが更新されました。",
    "reload": "再読み込み",
    "offline_unavailable": "オフラインのため、このページを表示できません。",
}


class PwaLocaleChromeError(RuntimeError):
    """Raised when localized PWA chrome violates its runtime contract."""


def _discover_japanese_pwa_page(site_root: Path) -> tuple[Path, str]:
    ja_root = site_root / "ja"
    if not ja_root.is_dir():
        raise PwaLocaleChromeError("built site has no Japanese publication root")
    for path in sorted(ja_root.rglob("index.html")):
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        if (
            '<html lang="ja"' not in source
            or 'rel="manifest" href="/app.webmanifest"' not in source
            or "/javascripts/pwa.js" not in source
        ):
            continue
        relative = path.relative_to(site_root)
        parent = relative.parent.as_posix()
        route = "/" if parent == "." else f"/{parent}/"
        return path, route
    raise PwaLocaleChromeError("built site has no Japanese PWA HTML page")


def _fixture_handler(site_root: Path) -> type[BaseHTTPRequestHandler]:
    resolved_root = site_root.resolve(strict=True)
    worker_source = (resolved_root / "service-worker.js").read_text(encoding="utf-8")
    test_hook = f"""
self.addEventListener("message", (event) => {{
  if (
    event.data?.type === {json.dumps(TEST_MESSAGE_TYPE)} &&
    event.source &&
    typeof event.source.postMessage === "function" &&
    typeof event.data.url === "string"
  ) {{
    event.source.postMessage({{
      type: "templates:freshness-state",
      state: "update-available",
      url: event.data.url,
      requestGeneration: 1000000,
      workerInstanceId: WORKER_INSTANCE_ID,
      awaitingCommit: false,
    }});
  }}
}});
"""
    worker_body = (worker_source + "\n" + test_hook).encode("utf-8")

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
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            request_path = unquote(urlsplit(self.path).path)
            if request_path == "/service-worker.js":
                self._send(worker_body, "text/javascript; charset=utf-8")
                return

            relative = request_path.lstrip("/")
            if not relative or request_path.endswith("/"):
                relative = f"{relative}index.html"
            candidate = (resolved_root / relative).resolve()
            try:
                candidate.relative_to(resolved_root)
            except ValueError:
                self._send(b"", "text/plain; charset=utf-8", status=404)
                return
            if not candidate.is_file():
                self._send(b"", "text/plain; charset=utf-8", status=404)
                return

            content_type, _ = mimetypes.guess_type(candidate.name)
            if candidate.suffix.lower() in {".html", ".css", ".js", ".json", ".svg"}:
                charset = "; charset=utf-8" if candidate.suffix.lower() != ".svg" else ""
                content_type = (content_type or "application/octet-stream") + charset
            self._send(candidate.read_bytes(), content_type or "application/octet-stream")

    return Handler


def _wait_for_document_cache(page: Any) -> None:
    page.wait_for_function(
        """async (cacheName) => {
          const cache = await caches.open(cacheName);
          return Boolean(await cache.match(window.location.href));
        }""",
        arg=DOCUMENT_CACHE_NAME,
    )


def run_check(site_root: Path, output: Path | None) -> dict[str, Any]:
    required = (
        site_root / "service-worker.js",
        site_root / "javascripts/pwa.js",
        site_root / "site-chrome-locales.json",
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise PwaLocaleChromeError(
            "built site is missing required PWA locale assets: "
            + ", ".join(path.as_posix() for path in missing)
        )
    page_path, route = _discover_japanese_pwa_page(site_root)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PwaLocaleChromeError("Playwright is required for PWA locale checks") from exc

    server = ThreadingHTTPServer(("127.0.0.1", 0), _fixture_handler(site_root))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    evidence: dict[str, Any] = {
        "base_url": base_url,
        "japanese_page": page_path.relative_to(site_root).as_posix(),
        "route": route,
    }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(service_workers="allow")
            page = context.new_page()
            response = page.goto(base_url + route, wait_until="load")
            if response is None or response.status != 200:
                raise PwaLocaleChromeError("Japanese PWA page did not load")
            page.evaluate("() => navigator.serviceWorker.ready.then(() => undefined)")
            page.wait_for_function("() => navigator.serviceWorker.controller !== null")

            # Reload once under Service Worker control so the document cache contains
            # the exact Japanese representation used for the offline assertions.
            response = page.reload(wait_until="load")
            if response is None or response.status != 200:
                raise PwaLocaleChromeError("controlled Japanese PWA reload failed")
            _wait_for_document_cache(page)

            page.evaluate(
                """(messageType) => {
                  navigator.serviceWorker.controller.postMessage({
                    type: messageType,
                    url: window.location.href,
                  });
                }""",
                TEST_MESSAGE_TYPE,
            )
            page.wait_for_function(
                """(expected) => {
                  const status = document.getElementById("templates-freshness-status");
                  return status && status.textContent.includes(expected);
                }""",
                arg=EXPECTED_JA["update_available"],
            )
            update_text = page.locator("#templates-freshness-status").inner_text()
            reload_text = page.locator("#templates-freshness-status button").inner_text()
            if EXPECTED_JA["published_changed"] not in update_text:
                raise PwaLocaleChromeError("Japanese update-available detail is missing")
            if reload_text != EXPECTED_JA["reload"]:
                raise PwaLocaleChromeError(
                    f"Japanese reload label mismatch: {reload_text!r}"
                )
            evidence["update_available"] = update_text
            evidence["reload_label"] = reload_text

            context.set_offline(True)
            response = page.reload(wait_until="load")
            if response is None or response.status != 200:
                status = None if response is None else response.status
                raise PwaLocaleChromeError(
                    f"Japanese cached fallback returned {status}, expected 200"
                )
            page.wait_for_selector("#templates-freshness-status")
            cached_text = page.locator("#templates-freshness-status").inner_text()
            if (
                EXPECTED_JA["saved_copy"] not in cached_text
                or EXPECTED_JA["unverified"] not in cached_text
            ):
                raise PwaLocaleChromeError(
                    f"Japanese cached warning mismatch: {cached_text!r}"
                )
            evidence["cached_unverified"] = cached_text

            miss = page.evaluate(
                """async () => {
                  const response = await fetch("/ja/__pwa-locale-cache-miss__/");
                  return { status: response.status, body: await response.text() };
                }"""
            )
            if (
                miss["status"] != 503
                or EXPECTED_JA["offline_unavailable"] not in miss["body"]
            ):
                raise PwaLocaleChromeError(
                    f"Japanese offline cache-miss response mismatch: {miss!r}"
                )
            evidence["offline_cache_miss"] = miss
            context.set_offline(False)
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evidence = run_check(args.site_root.resolve(), args.output)
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
