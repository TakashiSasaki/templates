#!/usr/bin/env python3
"""Run real-browser acceptance checks for the Site Composition Playground."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "docs" / "composition-playground.md"
FIXTURE = ROOT / "tests" / "fixtures" / "composition-playground-v1-explain.json"
CORE_JS = ROOT / "assets" / "javascripts" / "composition-playground.js"
EXPLAIN_JS = ROOT / "assets" / "javascripts" / "composition-playground-explain.js"
CSS = ROOT / "assets" / "stylesheets" / "composition-playground.css"
SERVICE_WORKER = ROOT / "assets" / "service-worker.js"
PROJECTION_PATH = "/composition/playground/composition-playground-v1.json.gz"
SEMANTIC_REVISION = "a" * 40
PROVIDER_REVISION = "b" * 40


class PlaygroundBrowserError(RuntimeError):
    pass


class ProjectionRaceController:
    """Delay exactly one projection response so replacement mounts can overtake it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mode: str | None = None
        self._consumed = False
        self.first_started = threading.Event()
        self.release_first = threading.Event()
        self.first_finished = threading.Event()

    def arm(self, mode: str) -> None:
        if mode not in {"success", "failure"}:
            raise ValueError(f"unsupported projection race mode: {mode}")
        with self._lock:
            self._mode = mode
            self._consumed = False
            self.first_started.clear()
            self.release_first.clear()
            self.first_finished.clear()

    def before_request(self, path: str) -> str | None:
        if path.split("?", 1)[0] != PROJECTION_PATH:
            return None
        with self._lock:
            if self._mode is None or self._consumed:
                return None
            self._consumed = True
            mode = self._mode
            self.first_started.set()
        if not self.release_first.wait(timeout=15):
            return "timeout"
        return mode

    def after_request(self) -> None:
        with self._lock:
            self._mode = None
        self.first_finished.set()


def playground_markup() -> str:
    text = DOCUMENT.read_text(encoding="utf-8")
    start = text.find('<div id="composition-playground"')
    end = text.find("\n\n## v1 scope", start)
    if start < 0 or end < 0:
        raise PlaygroundBrowserError("Playground reader markup could not be extracted")
    markup = text[start:end].strip()
    for marker in (
        "data-playground-app",
        "data-playground-semantic-revision",
        "data-playground-provider-revision",
        "data-playground-projection-id",
        "data-playground-explain",
        "data-playground-groups",
        "data-playground-contracts",
        "data-playground-material-tree",
    ):
        if marker not in markup:
            raise PlaygroundBrowserError(f"Playground reader markup is missing {marker}")
    return markup


def prepare_harness(root: Path) -> None:
    (root / "javascripts").mkdir(parents=True)
    (root / "stylesheets").mkdir(parents=True)
    (root / "composition" / "playground").mkdir(parents=True)
    shutil.copyfile(CORE_JS, root / "javascripts" / CORE_JS.name)
    shutil.copyfile(EXPLAIN_JS, root / "javascripts" / EXPLAIN_JS.name)
    shutil.copyfile(CSS, root / "stylesheets" / CSS.name)
    service_worker_source = SERVICE_WORKER.read_text(encoding="utf-8")
    static_assets_match = re.search(r"const STATIC_ASSETS = (\[[^;]+\]);", service_worker_source)
    if not static_assets_match:
        raise PlaygroundBrowserError("Service Worker static asset inventory is unavailable")
    shutil.copyfile(SERVICE_WORKER, root / "service-worker.js")
    locale_payload = {
        "schema_version": 1,
        "canonical_language": "en",
        "locales": [{
            "language": "en",
            "pwa_freshness": {
                field: field.replace("_", " ") for field in (
                    "saved_copy",
                    "checking",
                    "unverified",
                    "update_available",
                    "published_changed",
                    "reload",
                    "offline_unavailable",
                )
            },
        }],
    }
    for asset in json.loads(static_assets_match.group(1)):
        target = root / asset.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(
                json.dumps(locale_payload) if asset == "/site-chrome-locales.json" else "",
                encoding="utf-8",
            )
    raw_fixture = FIXTURE.read_bytes()
    (root / "composition" / "playground" / "composition-playground-v1.json.gz").write_bytes(
        gzip.compress(raw_fixture, compresslevel=9, mtime=0)
    )
    (root / "build-provenance.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "repository": "TakashiSasaki/templates",
                "site_commit": "c" * 40,
                "publication_commits": {
                    "composition": PROVIDER_REVISION,
                    "policy": "d" * 40,
                },
            }
        ),
        encoding="utf-8",
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Composition Playground acceptance</title>
  <style>html {{ box-sizing: border-box; }} *, *::before, *::after {{ box-sizing: inherit; }} body {{ margin: 0; padding: 1rem; font: 16px/1.5 sans-serif; }} main {{ width: 38rem; max-width: calc(100% - 2rem); margin-inline: auto; }}</style>
  <link rel="stylesheet" href="/stylesheets/composition-playground.css">
  <script>
    window.document$ = {{
      subscribers: [],
      subscribe(callback) {{ this.subscribers.push(callback); return {{ unsubscribe() {{}} }}; }},
      emit() {{ for (const callback of [...this.subscribers]) callback(); }}
    }};
    window.__playgroundProjectionFetchStarted = 0;
    window.__playgroundProjectionFetchSettled = 0;
    const playgroundNativeFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {{
      const url = typeof input === "string" ? input : input?.url || "";
      const isProjection = url.includes("{PROJECTION_PATH}");
      if (isProjection) window.__playgroundProjectionFetchStarted += 1;
      const request = playgroundNativeFetch(input, init);
      if (isProjection) {{
        request.then(
          () => {{ window.__playgroundProjectionFetchSettled += 1; }},
          () => {{ window.__playgroundProjectionFetchSettled += 1; }}
        );
      }}
      return request;
    }};
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/service-worker.js");
  </script>
  <script src="/javascripts/composition-playground.js" defer></script>
  <script src="/javascripts/composition-playground-explain.js" defer></script>
</head>
<body><main>{playground_markup()}</main></body>
</html>
"""
    for page_path in (
        root / "index.html",
        root / "playground" / "index.html",
        root / "home" / "index.html",
    ):
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(html, encoding="utf-8")


def serve(
    root: Path,
) -> tuple[ThreadingHTTPServer, threading.Thread, str, ProjectionRaceController]:
    race = ProjectionRaceController()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            race_mode = race.before_request(self.path)
            if race_mode is None:
                super().do_GET()
                return
            try:
                if race_mode == "success":
                    super().do_GET()
                elif race_mode == "failure":
                    body = b"deliberate stale projection failure"
                    self.send_response(503)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    body = b"projection race gate timed out"
                    self.send_response(504)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            finally:
                race.after_request()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, f"http://{host}:{port}/", race


def assert_mobile_layout(page: Any) -> None:
    metrics = page.evaluate(
        """() => ({
          innerWidth: window.innerWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          appHidden: document.querySelector('[data-playground-app]').hidden,
          explainHidden: document.querySelector('[data-playground-explain]').hidden
        })"""
    )
    if metrics["innerWidth"] != 360 or metrics["clientWidth"] != 360:
        raise PlaygroundBrowserError(f"unexpected mobile viewport metrics: {metrics}")
    if metrics["scrollWidth"] > metrics["clientWidth"] + 1:
        raise PlaygroundBrowserError(f"Playground has horizontal overflow at 360px: {metrics}")
    if metrics["appHidden"] or metrics["explainHidden"]:
        raise PlaygroundBrowserError(f"Playground did not become visible: {metrics}")


def assert_desktop_layout(page: Any) -> None:
    metrics = page.evaluate(
        """() => ({
          innerWidth: window.innerWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          readerWidth: document.querySelector('main')?.getBoundingClientRect().width || 0,
          appHidden: document.querySelector('[data-playground-app]').hidden
        })"""
    )
    if metrics["innerWidth"] != 1024 or metrics["clientWidth"] != 1024:
        raise PlaygroundBrowserError(f"unexpected desktop viewport metrics: {metrics}")
    if metrics["readerWidth"] >= 800 or metrics["scrollWidth"] > metrics["clientWidth"] + 1:
        raise PlaygroundBrowserError(f"Playground desktop reader column overflows: {metrics}")
    if metrics["appHidden"]:
        raise PlaygroundBrowserError(f"Playground did not become visible at desktop width: {metrics}")


def assert_stale_navigation_race(
    browser: Any,
    base_url: str,
    race: ProjectionRaceController,
    mode: str,
) -> None:
    race.arm(mode)
    context = browser.new_context(
        viewport={"width": 360, "height": 800},
        service_workers="block",
    )
    page = context.new_page()
    page_errors: list[str] = []
    provider_requests: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "request",
        lambda request: provider_requests.append(request.url)
        if request.url.endswith(PROJECTION_PATH)
        else None,
    )
    try:
        page.goto(f"{base_url}playground/", wait_until="domcontentloaded")
        if not race.first_started.wait(timeout=5):
            raise PlaygroundBrowserError(f"{mode} stale-race request did not reach the delay gate")
        if page.evaluate("() => window.__playgroundProjectionFetchStarted") != 1:
            raise PlaygroundBrowserError(f"{mode} stale-race did not start exactly one initial projection load")

        page.evaluate(
            """markup => {
              const oldRoot = document.getElementById("composition-playground");
              if (oldRoot) oldRoot.dataset.raceGeneration = "A";
              history.pushState({}, "", "/home/");
              document.body.innerHTML = "<main><p>Home</p></main>";
              window.document$.emit();
              history.pushState({}, "", "/playground/");
              document.body.innerHTML = `<main>${markup}</main>`;
              const replacement = document.getElementById("composition-playground");
              replacement.dataset.raceGeneration = "B";
              window.document$.emit();
            }""",
            playground_markup(),
        )
        page.wait_for_selector("[data-playground-app]:not([hidden])")
        page.wait_for_selector("[data-playground-explain]:not([hidden])")
        if page.evaluate("() => window.__playgroundProjectionFetchStarted") != 2:
            raise PlaygroundBrowserError(f"{mode} stale-race replacement did not perform one projection load")
        before_release = page.evaluate(
            """() => ({
              generation: document.getElementById('composition-playground')?.dataset.raceGeneration,
              appHidden: document.querySelector('[data-playground-app]')?.hidden,
              explainHidden: document.querySelector('[data-playground-explain]')?.hidden,
              provider: document.querySelector('[data-playground-provider-revision]')?.textContent,
              semantic: document.querySelector('[data-playground-semantic-revision]')?.textContent
            })"""
        )
        if before_release != {
            "generation": "B",
            "appHidden": False,
            "explainHidden": False,
            "provider": PROVIDER_REVISION,
            "semantic": SEMANTIC_REVISION,
        }:
            raise PlaygroundBrowserError(f"{mode} replacement mount was not current before stale release: {before_release}")

        race.release_first.set()
        if not race.first_finished.wait(timeout=5):
            raise PlaygroundBrowserError(f"{mode} stale-race response did not finish")
        page.wait_for_function("() => window.__playgroundProjectionFetchSettled >= 2")
        state = page.evaluate(
            """async () => {
              await new Promise((resolve) => setTimeout(resolve, 0));
              const root = document.getElementById("composition-playground");
              const context = await window.CompositionPlayground.ensureMounted(document);
              return {
                generation: root?.dataset.raceGeneration,
                appHidden: document.querySelector('[data-playground-app]')?.hidden,
                explainHidden: document.querySelector('[data-playground-explain]')?.hidden,
                status: document.querySelector('[data-playground-status]')?.textContent || '',
                error: root?.dataset.playgroundError || null,
                sameContextRoot: context?.root === root,
                provider: context?.provenance?.providerRevision || null,
                semantic: context?.projection?.semanticRevision || null,
                subscribers: window.document$.subscribers.length,
                started: window.__playgroundProjectionFetchStarted,
                settled: window.__playgroundProjectionFetchSettled
              };
            }"""
        )
        expected_status = "Canonical Composition projection loaded with exact Site publication provenance."
        if (
            state["generation"] != "B"
            or state["appHidden"]
            or state["explainHidden"]
            or state["status"] != expected_status
            or state["error"] is not None
            or not state["sameContextRoot"]
            or state["provider"] != PROVIDER_REVISION
            or state["semantic"] != SEMANTIC_REVISION
            or state["subscribers"] != 2
            or state["started"] != 2
            or state["settled"] != 2
        ):
            raise PlaygroundBrowserError(f"{mode} stale mount mutated replacement state: {state}")
        if len(provider_requests) != 2:
            raise PlaygroundBrowserError(
                f"{mode} stale-race expected one projection request per mount cycle: {provider_requests}"
            )
        if page_errors:
            raise PlaygroundBrowserError(f"{mode} stale-race browser errors: {page_errors}")
    finally:
        race.release_first.set()
        context.close()


def run_browser_check() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaygroundBrowserError(
            "Playwright is required; install requirements-visual.txt"
        ) from exc

    with tempfile.TemporaryDirectory(prefix="composition-playground-browser-") as directory:
        harness = Path(directory)
        prepare_harness(harness)
        server, thread, base_url, race = serve(harness)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()

                # Deterministically reproduce both stale-success and stale-failure
                # continuations while replacement root B is already current.
                assert_stale_navigation_race(browser, base_url, race, "success")
                assert_stale_navigation_race(browser, base_url, race, "failure")

                context = browser.new_context(viewport={"width": 360, "height": 800})
                page = context.new_page()
                page_errors: list[str] = []
                provider_requests: list[str] = []
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.on("request", lambda request: provider_requests.append(request.url) if request.url.endswith(PROJECTION_PATH) else None)
                page.goto(base_url, wait_until="networkidle")
                page.wait_for_selector("[data-playground-app]:not([hidden])")
                page.wait_for_selector("[data-playground-explain]:not([hidden])")
                if len(provider_requests) != 1:
                    raise PlaygroundBrowserError(f"expected one initial projection request, got {provider_requests}")
                assert_mobile_layout(page)
                page.set_viewport_size({"width": 1024, "height": 900})
                page.reload(wait_until="networkidle")
                page.wait_for_selector("[data-playground-explain]:not([hidden])")
                assert_desktop_layout(page)
                page.set_viewport_size({"width": 360, "height": 800})
                page.reload(wait_until="networkidle")
                page.wait_for_selector("[data-playground-explain]:not([hidden])")
                assert_mobile_layout(page)

                if page.locator("[data-playground-semantic-revision]").text_content() != SEMANTIC_REVISION:
                    raise PlaygroundBrowserError("semantic source revision did not render from projection")
                if page.locator("[data-playground-provider-revision]").text_content() != PROVIDER_REVISION:
                    raise PlaygroundBrowserError("provider revision did not render from Site build provenance")
                if page.locator("[data-playground-projection-id]").text_content() != "composition-playground-v1":
                    raise PlaygroundBrowserError("projection identity did not render")

                recipe = page.locator("[data-playground-recipe]")
                recipe.focus()
                page.keyboard.press("Tab")
                active = page.evaluate(
                    """() => ({tag: document.activeElement?.tagName, type: document.activeElement?.type, value: document.activeElement?.value})"""
                )
                if active != {"tag": "INPUT", "type": "checkbox", "value": "capability.cli"}:
                    raise PlaygroundBrowserError(f"keyboard order did not reach first optional component: {active}")
                page.keyboard.press("Space")
                page.wait_for_function("() => location.hash.includes('include=capability.cli')")
                page.wait_for_function(
                    "() => Array.from(document.querySelectorAll('[data-playground-resolved] li')).some((node) => node.textContent === 'foundation.web')"
                )

                explanation = page.locator("[data-playground-explain]").text_content() or ""
                for expected in (
                    "foundation.web",
                    "Required directly by capability.cli.",
                    "cli-interface",
                    "routes.json — foundation.web; ownership: generated",
                    "Canonical empty-target initial plan: 3 create.",
                ):
                    if expected not in explanation:
                        raise PlaygroundBrowserError(f"explainability output is missing {expected!r}")

                details = page.locator("[data-playground-explain] > details").first
                summary = details.locator(":scope > summary")
                summary.focus()
                if not details.evaluate("node => node.open"):
                    raise PlaygroundBrowserError("first explainability disclosure should start open")
                page.keyboard.press("Enter")
                if details.evaluate("node => node.open"):
                    raise PlaygroundBrowserError("Enter did not close native details disclosure")
                page.keyboard.press("Enter")
                if not details.evaluate("node => node.open"):
                    raise PlaygroundBrowserError("Enter did not reopen native details disclosure")

                assert_mobile_layout(page)
                page.reload(wait_until="networkidle")
                page.wait_for_selector("[data-playground-explain]:not([hidden])")
                if not page.locator('input[type="checkbox"][value="capability.cli"]').is_checked():
                    raise PlaygroundBrowserError("shareable URL hash did not restore the selected component")
                assert_mobile_layout(page)
                markup = playground_markup()
                for _cycle in range(2):
                    before_requests = len(provider_requests)
                    page.evaluate(
                        """markup => {
                          history.pushState({}, "", "/home/");
                          document.body.innerHTML = "<main><p>Home</p></main>";
                          window.document$.emit();
                          history.pushState({}, "", "/playground/");
                          document.body.innerHTML = markup;
                          window.document$.emit();
                        }""",
                        markup,
                    )
                    page.wait_for_selector("[data-playground-explain]:not([hidden])")
                    if len(provider_requests) != before_requests + 1:
                        raise PlaygroundBrowserError(
                            "instant navigation mounted the projection more than once: "
                            f"{provider_requests[before_requests:]}"
                        )
                    assert_mobile_layout(page)
                if page.evaluate("() => window.document$.subscribers.length") != 2:
                    raise PlaygroundBrowserError("instant navigation accumulated duplicate lifecycle subscribers")

                page.evaluate("() => navigator.serviceWorker.ready")
                page.wait_for_function("() => navigator.serviceWorker.controller !== null")
                page.reload(wait_until="networkidle")
                page.wait_for_selector("[data-playground-explain]:not([hidden])")
                page.evaluate(
                    """async () => {
                      const html = "<!doctype html>" + document.documentElement.outerHTML;
                      const cache = await caches.open("templates-portal-documents-v1");
                      await cache.put(
                        new Request("/playground/"),
                        new Response(html, {
                          status: 200,
                          headers: {"content-type": "text/html; charset=utf-8"}
                        })
                      );
                    }"""
                )
                context.set_offline(True)
                page.reload(wait_until="domcontentloaded")
                page.wait_for_function(
                    "() => document.querySelector('[data-playground-status]')?.textContent !== "
                    "'Loading the canonical Composition projection…'"
                )
                offline_metrics = page.evaluate(
                    """() => ({
                      hasRoot: Boolean(document.querySelector('#composition-playground')),
                      appHidden: document.querySelector('[data-playground-app]')?.hidden,
                      explainHidden: document.querySelector('[data-playground-explain]')?.hidden,
                      status: document.querySelector('[data-playground-status]')?.textContent || ''
                    })"""
                )
                context.set_offline(False)
                if not offline_metrics["hasRoot"] or not offline_metrics["appHidden"] or not offline_metrics["explainHidden"] or "not available" not in offline_metrics["status"]:
                    raise PlaygroundBrowserError(
                        f"offline cached HTML did not execute fail-closed runtime: {offline_metrics}"
                    )
                if page_errors:
                    raise PlaygroundBrowserError(f"browser page errors: {page_errors}")
                context.close()
                browser.close()
        finally:
            race.release_first.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description=__doc__).parse_args()


def main() -> int:
    parse_args()
    try:
        run_browser_check()
    except (OSError, PlaygroundBrowserError) as exc:
        raise SystemExit(str(exc)) from exc
    print("Composition Playground browser acceptance passed at 360px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
