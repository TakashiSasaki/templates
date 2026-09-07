#!/usr/bin/env python3
"""Exercise WebMCP Default/Adopt/Explicitly-exclude against an assembled Site."""
from __future__ import annotations

import argparse
import gzip
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class BrowserError(RuntimeError):
    pass


def serve(root: Path) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(root), **kwargs)
        def log_message(self, format: str, *args: Any) -> None:
            return
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, f"http://{host}:{port}"


def read_gzip_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(gzip.decompress(path.read_bytes()))
    except (OSError, EOFError, gzip.BadGzipFile, json.JSONDecodeError) as exc:
        raise BrowserError(f"cannot decode assembled provider projection {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BrowserError(f"assembled provider projection must be an object: {path}")
    return value


def validate_projection_pair(site_root: Path) -> str:
    base_path = site_root / "composition" / "playground" / "composition-playground-v1.json.gz"
    intent_path = site_root / "composition" / "playground" / "composition-playground-intent-v1.json.gz"
    base = read_gzip_json(base_path)
    intent = read_gzip_json(intent_path)
    if base.get("projection_id") != "composition-playground-v1":
        raise BrowserError("assembled resolution projection identity is invalid")
    if intent.get("projection_id") != "composition-playground-intent-v1":
        raise BrowserError("assembled intent projection identity is invalid")
    if intent.get("resolution_projection_id") != "composition-playground-v1":
        raise BrowserError("assembled intent projection does not target the canonical resolution projection")
    if intent.get("strategy") != "indexed-single-explicit-exclusion-transitions":
        raise BrowserError("assembled intent projection strategy is invalid")
    base_revision = base.get("source", {}).get("revision")
    if not isinstance(base_revision, str) or intent.get("source", {}).get("revision") != base_revision:
        raise BrowserError("assembled resolution and intent projections have different semantic revisions")
    website = next((r for r in intent.get("recipes", []) if r.get("id") == "website"), None)
    if not website or "capability.webmcp" not in website.get("optional_components", []):
        raise BrowserError("assembled intent projection does not expose Website WebMCP intent")
    return base_revision


def run(site_root: Path) -> None:
    semantic_revision = validate_projection_pair(site_root)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserError("Playwright is required") from exc

    server, thread, base_url = serve(site_root)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome")
            page = browser.new_page(viewport={"width": 1024, "height": 900})
            errors: list[str] = []
            intent_requests: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "request",
                lambda request: intent_requests.append(request.url)
                if request.url.endswith("/composition/playground/composition-playground-intent-v1.json.gz")
                else None,
            )
            page.goto(f"{base_url}/playground/#recipe=website", wait_until="networkidle")
            page.wait_for_selector("[data-playground-app]:not([hidden])")
            page.wait_for_function("() => document.querySelector('[data-playground-webmcp-status]')?.textContent.includes('Default:')")

            root = page.locator("#composition-playground")
            if root.get_attribute("data-playground-webmcp-error"):
                raise BrowserError("WebMCP enhancer failed during initial mount")
            if len(intent_requests) != 1:
                raise BrowserError(f"expected exactly one intent projection request for initial mount: {intent_requests}")
            if page.locator("[data-playground-semantic-revision]").text_content() != semantic_revision:
                raise BrowserError("browser semantic revision differs from assembled projection")

            webmcp = page.locator('input[type="checkbox"][value="capability.webmcp"]')
            if webmcp.count() != 1 or webmcp.is_checked():
                raise BrowserError("Website Default must expose WebMCP as optional and unspecified")
            if not page.locator('input[name="playground-webmcp-intent"][value="default"]').is_checked():
                raise BrowserError("Default WebMCP radio is not selected")

            page.locator('input[name="playground-webmcp-intent"][value="adopt"]').check()
            page.wait_for_function("() => location.hash.includes('include=capability.webmcp')")
            page.wait_for_function("() => document.querySelector('[data-playground-webmcp-status]')?.textContent.includes('Adopt:')")
            if not webmcp.is_checked():
                raise BrowserError("Adopt did not delegate to canonical explicit include selection")
            adopted = page.locator("[data-playground-resolved]").text_content() or ""
            if "capability.webmcp" not in adopted:
                raise BrowserError("canonical adopted outcome does not contain capability.webmcp")

            page.locator('input[name="playground-webmcp-intent"][value="exclude"]').check()
            page.wait_for_function("() => !location.hash.includes('include=capability.webmcp')")
            page.wait_for_selector("[data-playground-webmcp-result]:not([hidden])")
            page.wait_for_function("() => document.querySelector('[data-playground-webmcp-status]')?.textContent.includes('provider-resolved transition')")
            if webmcp.is_checked():
                raise BrowserError("Explicit exclusion left WebMCP explicitly included")
            config = json.loads(page.locator("[data-playground-webmcp-config]").text_content() or "{}")
            if config.get("components") != {"include": [], "exclude": ["capability.webmcp"]}:
                raise BrowserError(f"explicit exclusion configuration is wrong: {config}")
            validity = page.locator("[data-playground-webmcp-validity]").text_content() or ""
            if "valid according to the canonical Composition provider" not in validity:
                raise BrowserError(f"explicit exclusion did not use canonical provider validity: {validity}")
            excluded = page.locator("[data-playground-webmcp-resolved]").text_content() or ""
            if "capability.webmcp" in excluded:
                raise BrowserError("provider-resolved explicit exclusion still contains capability.webmcp")
            if errors:
                raise BrowserError(f"browser page errors: {errors}")
            browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.site_root)
    except (OSError, ValueError, BrowserError) as exc:
        raise SystemExit(str(exc)) from exc
    print("Composition Playground WebMCP tri-state browser acceptance passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
