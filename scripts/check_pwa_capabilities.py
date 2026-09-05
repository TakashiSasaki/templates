#!/usr/bin/env python3
"""Exercise the Service Worker freshness-capability message contract in Chromium."""

from __future__ import annotations

import argparse
import json
import re
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import check_pwa_freshness


EXPECTED_STATES = [
    "verified-current",
    "checking",
    "cached-unverified",
    "update-available",
]
EXPECTED_SITE_VERSION_URL = "/site-version.json"
EXPECTED_DOCUMENT_CACHE_NAME = "templates-portal-documents-v1"
EXPECTED_GLOSSARY_CACHE_NAME = "templates-portal-glossary-v1"
EXPECTED_GLOSSARY_MODEL_URL = "/glossary/index.json"
EXPECTED_SOFT_TIMEOUT_MS = 1500
STATIC_ASSETS_PATTERN = re.compile(r"const STATIC_ASSETS = (\[[^;]+\]);", re.DOTALL)


class PwaCapabilityError(RuntimeError):
    """Raised when the live Service Worker capability contract is unavailable or invalid."""


def _read_install_assets(site_root: Path) -> list[Path]:
    worker_path = site_root / "service-worker.js"
    if not worker_path.is_file():
        return [worker_path]
    source = worker_path.read_text(encoding="utf-8")
    match = STATIC_ASSETS_PATTERN.search(source)
    if match is None:
        raise PwaCapabilityError("service worker STATIC_ASSETS declaration is unavailable")
    try:
        asset_urls = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise PwaCapabilityError("service worker STATIC_ASSETS declaration is not JSON-compatible") from exc
    if not isinstance(asset_urls, list) or any(
        not isinstance(asset, str) or not asset.startswith("/") or ".." in asset.split("/")
        for asset in asset_urls
    ):
        raise PwaCapabilityError("service worker STATIC_ASSETS declaration contains an unsafe asset path")
    return [worker_path, *(site_root / asset.lstrip("/") for asset in asset_urls)]


def _read_capabilities(page: Any) -> dict[str, Any] | None:
    return page.evaluate(
        """async () => {
          const worker = navigator.serviceWorker.controller;
          if (!worker) return null;
          navigator.serviceWorker.startMessages();
          return await new Promise((resolve) => {
            const timer = setTimeout(() => {
              navigator.serviceWorker.removeEventListener("message", onMessage);
              resolve(null);
            }, 5000);
            const onMessage = (event) => {
              if (event.data?.type === "templates:freshness-capabilities") {
                clearTimeout(timer);
                navigator.serviceWorker.removeEventListener("message", onMessage);
                resolve(event.data);
              }
            };
            navigator.serviceWorker.addEventListener("message", onMessage);
            worker.postMessage({ type: "templates:get-freshness-capabilities" });
          });
        }"""
    )


def run_check(site_root: Path, output: Path | None) -> dict[str, Any]:
    required = _read_install_assets(site_root)
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise PwaCapabilityError(
            "built site is missing required PWA assets: "
            + ", ".join(path.as_posix() for path in missing)
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PwaCapabilityError("Playwright is required for PWA capability checks") from exc

    state = check_pwa_freshness.FixtureState()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        check_pwa_freshness._fixture_handler(site_root, state),
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome")
            context = browser.new_context(service_workers="allow")
            page = context.new_page()
            page.goto(base_url + "/", wait_until="load")
            page.evaluate("() => navigator.serviceWorker.ready.then(() => undefined)")
            page.wait_for_function("() => navigator.serviceWorker.controller !== null")
            check_pwa_freshness._wait_for_worker_version(page, 1)
            capabilities = _read_capabilities(page)
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

    if capabilities is None:
        raise PwaCapabilityError("freshness capability request timed out")
    if capabilities.get("states") != EXPECTED_STATES:
        raise PwaCapabilityError(f"unexpected freshness state vocabulary: {capabilities!r}")
    if capabilities.get("siteVersionUrl") != EXPECTED_SITE_VERSION_URL:
        raise PwaCapabilityError(f"unexpected freshness siteVersionUrl: {capabilities!r}")
    if capabilities.get("documentCacheName") != EXPECTED_DOCUMENT_CACHE_NAME:
        raise PwaCapabilityError(f"unexpected freshness documentCacheName: {capabilities!r}")
    if capabilities.get("glossaryCacheName") != EXPECTED_GLOSSARY_CACHE_NAME:
        raise PwaCapabilityError(f"unexpected freshness glossaryCacheName: {capabilities!r}")
    if capabilities.get("glossaryModelUrl") != EXPECTED_GLOSSARY_MODEL_URL:
        raise PwaCapabilityError(f"unexpected freshness glossaryModelUrl: {capabilities!r}")
    if capabilities.get("softTimeoutMs") != EXPECTED_SOFT_TIMEOUT_MS:
        raise PwaCapabilityError(f"unexpected freshness softTimeoutMs: {capabilities!r}")
    worker_instance_id = capabilities.get("workerInstanceId")
    if not isinstance(worker_instance_id, str) or not worker_instance_id:
        raise PwaCapabilityError(f"unexpected freshness workerInstanceId: {capabilities!r}")

    evidence = {"base_url": base_url, "capabilities": capabilities}
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
