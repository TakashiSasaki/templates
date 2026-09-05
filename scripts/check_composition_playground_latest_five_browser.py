#!/usr/bin/env python3
"""Real Pages-artifact acceptance for the latest five Playground remediations."""

from __future__ import annotations

import argparse
import json
import os
import threading
from collections import Counter
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


PROJECTION_PATH = "/composition/playground/composition-playground-v1.json.gz"
PROVENANCE_PATH = "/build-provenance.json"
PLAYGROUND_PATH = "/playground/"


class AvailabilityState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.fail_projection = False
        self.fail_provenance = False
        self.counts: Counter[str] = Counter()

    def record(self, path: str) -> bool:
        with self.lock:
            if path == PROJECTION_PATH:
                self.counts["projection"] += 1
                return self.fail_projection
            if path == PROVENANCE_PATH:
                self.counts["provenance"] += 1
                return self.fail_provenance
            return False

    def projection_count(self) -> int:
        with self.lock:
            return self.counts["projection"]

    def provenance_count(self) -> int:
        with self.lock:
            return self.counts["provenance"]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str, state: AvailabilityState, **kwargs) -> None:
        self.state = state
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlsplit(self.path).path
        if self.state.record(path):
            self.send_response(503)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"temporarily unavailable")
            return
        super().do_GET()


def start_server(site_root: Path) -> tuple[ThreadingHTTPServer, AvailabilityState, str]:
    state = AvailabilityState()
    handler = partial(Handler, directory=str(site_root), state=state)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, state, f"http://{host}:{port}"


def assert_exact_built_provenance(page, site_root: Path) -> None:
    provenance = json.loads((site_root / "build-provenance.json").read_text(encoding="utf-8"))
    expected_site = os.environ.get("EXPECTED_SITE_REVISION")
    expected_provider = os.environ.get("EXPECTED_PROVIDER_REVISION")
    expected_semantic = os.environ.get("EXPECTED_SEMANTIC_REVISION")

    document_revision = page.locator('meta[name="templates-site-revision"]').get_attribute("content")
    assert document_revision == provenance["site_commit"], (
        f"built document revision {document_revision!r} does not match build provenance "
        f"{provenance['site_commit']!r}"
    )
    if expected_site:
        assert document_revision == expected_site
    if expected_provider:
        assert provenance["publication_commits"]["composition"] == expected_provider
        assert page.locator("[data-playground-provider-revision]").inner_text().strip() == expected_provider
    if expected_semantic:
        assert page.locator("[data-playground-semantic-revision]").inner_text().strip() == expected_semantic
        if expected_provider:
            assert expected_semantic != expected_provider, "semantic source and provider identities must remain distinct"


def assert_focus_continuity(page) -> None:
    checkbox = page.locator('[data-playground-optionals] input[type="checkbox"]').first
    assert checkbox.count() == 1, "canonical Pages artifact must expose at least one optional checkbox"
    component_id = checkbox.get_attribute("value")
    assert component_id

    checkbox.focus()
    page.keyboard.press("Space")
    page.wait_for_function(
        "component => document.activeElement && document.activeElement.type === 'checkbox' && document.activeElement.value === component",
        arg=component_id,
    )
    first_checked = page.locator(
        f'[data-playground-optionals] input[type="checkbox"][value="{component_id}"]'
    ).is_checked()
    first_config = json.loads(page.locator("[data-playground-config]").inner_text())
    assert (component_id in first_config["components"]["include"]) == first_checked
    first_hash = page.evaluate("location.hash")

    page.keyboard.press("Space")
    page.wait_for_function(
        "component => document.activeElement && document.activeElement.type === 'checkbox' && document.activeElement.value === component",
        arg=component_id,
    )
    second_checked = page.locator(
        f'[data-playground-optionals] input[type="checkbox"][value="{component_id}"]'
    ).is_checked()
    second_config = json.loads(page.locator("[data-playground-config]").inner_text())
    assert (component_id in second_config["components"]["include"]) == second_checked
    second_hash = page.evaluate("location.hash")
    assert first_hash != second_hash, "share-state hash must follow keyboard selection changes"


def assert_document_provenance_mismatch_fails_closed(browser, base_url: str, site_root: Path) -> None:
    provenance = json.loads((site_root / "build-provenance.json").read_text(encoding="utf-8"))
    mismatch = dict(provenance)
    mismatch["site_commit"] = "0" * 40 if provenance["site_commit"] != "0" * 40 else "1" * 40

    context = browser.new_context(service_workers="block")
    page = context.new_page()
    page.route(
        f"**{PROVENANCE_PATH}",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(mismatch),
        ),
    )
    page.goto(f"{base_url}{PLAYGROUND_PATH}", wait_until="domcontentloaded")
    page.locator('#composition-playground[data-playground-error="MALFORMED_PROVENANCE"]').wait_for()
    assert page.locator("[data-playground-app]").is_hidden()
    assert page.locator("[data-playground-explain]").is_hidden()
    context.close()


def assert_transient_recovery(browser, base_url: str, state: AvailabilityState) -> None:
    before = state.projection_count()
    state.fail_projection = True
    context = browser.new_context(service_workers="block", viewport={"width": 360, "height": 900})
    page = context.new_page()
    page.goto(f"{base_url}{PLAYGROUND_PATH}#recipe=skill", wait_until="domcontentloaded")
    page.locator('#composition-playground[data-playground-error="PROJECTION_UNAVAILABLE"]').wait_for()
    assert page.locator("[data-playground-app]").is_hidden()
    assert page.locator("[data-playground-explain]").is_hidden()
    marker = page.evaluate("window.__latestFiveRecoveryMarker = Math.random().toString(36); window.__latestFiveRecoveryMarker")
    failed_hash = page.evaluate("location.hash")

    state.fail_projection = False
    page.evaluate("window.dispatchEvent(new Event('online'))")
    page.locator("[data-playground-app]").wait_for(state="visible")
    page.locator("[data-playground-explain]").wait_for(state="visible")
    assert page.evaluate("window.__latestFiveRecoveryMarker") == marker, "recovery must not reload the document"
    assert page.evaluate("location.hash") == failed_hash, "retry must preserve the current share-state hash"
    assert state.projection_count() - before == 2, "one failed projection request plus one legitimate retry is expected"

    page.evaluate("window.dispatchEvent(new Event('online'))")
    page.evaluate(
        "Promise.all([CompositionPlayground.ensureMounted(document), CompositionPlayground.ensureMounted(document), CompositionPlayground.ensureMounted(document)])"
    )
    page.wait_for_timeout(100)
    assert state.projection_count() - before == 2, "repeated recovery signals must not duplicate projection loads"
    assert page.locator("[data-playground-explain]").count() == 1
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")

    assert_focus_continuity(page)
    context.close()


def assert_provenance_transient_recovery(browser, base_url: str, state: AvailabilityState) -> None:
    before = state.provenance_count()
    state.fail_provenance = True
    context = browser.new_context(service_workers="block", viewport={"width": 360, "height": 900})
    page = context.new_page()
    page.goto(f"{base_url}{PLAYGROUND_PATH}#recipe=skill", wait_until="domcontentloaded")
    page.locator('#composition-playground[data-playground-error="PROVENANCE_UNAVAILABLE"]').wait_for()
    assert page.locator("[data-playground-app]").is_hidden()
    assert page.locator("[data-playground-explain]").is_hidden()
    marker = page.evaluate("window.__latestFiveProvenanceRecoveryMarker = Math.random().toString(36); window.__latestFiveProvenanceRecoveryMarker")
    failed_hash = page.evaluate("location.hash")

    state.fail_provenance = False
    page.evaluate("window.dispatchEvent(new Event('online'))")
    page.locator("[data-playground-app]").wait_for(state="visible")
    page.locator("[data-playground-explain]").wait_for(state="visible")
    assert page.evaluate("window.__latestFiveProvenanceRecoveryMarker") == marker
    assert page.evaluate("location.hash") == failed_hash
    assert state.provenance_count() - before == 2, "one failed provenance request plus one legitimate retry is expected"

    page.evaluate("window.dispatchEvent(new Event('online'))")
    page.evaluate(
        "Promise.all([CompositionPlayground.ensureMounted(document), CompositionPlayground.ensureMounted(document), CompositionPlayground.ensureMounted(document)])"
    )
    page.wait_for_timeout(100)
    assert state.provenance_count() - before == 2, "repeated recovery signals must not duplicate provenance loads"
    context.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", type=Path, required=True)
    args = parser.parse_args()
    site_root = args.site_root.resolve()
    assert (site_root / "playground" / "index.html").is_file()
    assert (site_root / "build-provenance.json").is_file()
    assert (site_root / PROJECTION_PATH.lstrip("/")).is_file()

    server, state, base_url = start_server(site_root)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()

            context = browser.new_context(service_workers="block", viewport={"width": 1280, "height": 900})
            page = context.new_page()
            page.goto(f"{base_url}{PLAYGROUND_PATH}", wait_until="domcontentloaded")
            page.locator("[data-playground-app]").wait_for(state="visible")
            page.locator("[data-playground-explain]").wait_for(state="visible")
            assert_exact_built_provenance(page, site_root)
            context.close()

            assert_document_provenance_mismatch_fails_closed(browser, base_url, site_root)
            assert_provenance_transient_recovery(browser, base_url, state)
            assert_transient_recovery(browser, base_url, state)
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
