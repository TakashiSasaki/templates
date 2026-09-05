#!/usr/bin/env python3
"""Exercise slow-network PWA freshness convergence in Chromium."""

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

import check_pwa_capabilities


DOCUMENT_CACHE_NAME = "templates-portal-documents-v1"
REVISION_V1 = "1" * 40
REVISION_V2 = "2" * 40
REVISION_V3 = "3" * 40
REVISION_V4 = "4" * 40
REVISION_V5 = "5" * 40
REVISION_V6 = "6" * 40
REVISION_V7 = "7" * 40
FETCH_CHECK_TIMEOUT_MS = 10_000
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


class PwaSlowConvergenceError(RuntimeError):
    """Raised when Chromium violates the slow-network convergence contract."""


@dataclass
class SlowFixtureState:
    document_version: int = 1
    document_revision: str = REVISION_V1
    document_status: int = 200
    document_delay_ms: int = 0
    document_content_type: str = "text/html; charset=utf-8"
    include_revision: bool = True
    reverse_revision_attributes: bool = False
    document_hits: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def configure(
        self,
        *,
        version: int | None = None,
        revision: str | None = None,
        status: int | None = None,
        delay_ms: int | None = None,
        content_type: str | None = None,
        include_revision: bool | None = None,
        reverse_revision_attributes: bool | None = None,
    ) -> None:
        with self.lock:
            if version is not None:
                self.document_version = version
            if revision is not None:
                self.document_revision = revision
            if status is not None:
                self.document_status = status
            if delay_ms is not None:
                self.document_delay_ms = delay_ms
            if content_type is not None:
                self.document_content_type = content_type
            if include_revision is not None:
                self.include_revision = include_revision
            if reverse_revision_attributes is not None:
                self.reverse_revision_attributes = reverse_revision_attributes

    def snapshot(self) -> tuple[int, str, int, int, str, bool, bool]:
        with self.lock:
            self.document_hits += 1
            return (
                self.document_version,
                self.document_revision,
                self.document_status,
                self.document_delay_ms,
                self.document_content_type,
                self.include_revision,
                self.reverse_revision_attributes,
            )


def _fixture_handler(site_root: Path, state: SlowFixtureState) -> type[BaseHTTPRequestHandler]:
    resolved_site_root = site_root.resolve()
    worker_source = (resolved_site_root / "service-worker.js").read_bytes()
    pwa_source = (resolved_site_root / "javascripts/pwa.js").read_bytes()

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
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        def _send_static_asset(self, path: str) -> bool:
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

        def _document_body(
            self,
            version: int,
            revision: str,
            content_type: str,
            include_revision: bool,
            reverse_revision_attributes: bool,
        ) -> bytes:
            if not content_type.lower().startswith("text/html"):
                return json.dumps({"version": version, "revision": revision}).encode("utf-8")
            if include_revision:
                if reverse_revision_attributes:
                    revision_meta = (
                        f'<meta data-fixture="ordered" content="{revision}" '
                        'name="templates-site-revision">'
                    )
                else:
                    revision_meta = (
                        f'<meta name="templates-site-revision" data-fixture="ordered" '
                        f'content="{revision}">'
                    )
            else:
                revision_meta = ""
            return (
                "<!doctype html><html><head><meta charset=\"utf-8\">"
                + revision_meta
                + '<link rel="stylesheet" href="/stylesheets/freshness-status.css">'
                + "<title>Slow document fixture</title></head><body>"
                + f'<main id="document-version">document-v{version}</main>'
                + DOCUMENT_OBSERVABLE_FIXTURE
                + '<script src="/javascripts/pwa.js"></script>'
                + "</body></html>"
            ).encode("utf-8")

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/":
                self._send(
                    (
                        "<!doctype html><html><head><meta charset=\"utf-8\">"
                        '<link rel="stylesheet" href="/stylesheets/freshness-status.css">'
                        "<title>Slow freshness fixture</title></head><body><main>root</main>"
                        + DOCUMENT_OBSERVABLE_FIXTURE
                        + '<script src="/javascripts/pwa.js"></script></body></html>'
                    ).encode("utf-8"),
                    "text/html; charset=utf-8",
                )
                return
            if path == "/service-worker.js":
                self._send(worker_source, "text/javascript; charset=utf-8")
                return
            if path == "/javascripts/pwa.js":
                self._send(pwa_source, "text/javascript; charset=utf-8")
                return
            if path in {
                "/document",
                "/document/",
                "/document/index.html",
                "/uncached",
                "/uncached/",
                "/uncached/index.html",
            }:
                (
                    version,
                    revision,
                    status,
                    delay_ms,
                    content_type,
                    include_revision,
                    reverse_revision_attributes,
                ) = state.snapshot()
                if delay_ms:
                    time.sleep(delay_ms / 1000)
                body = self._document_body(
                    version,
                    revision,
                    content_type,
                    include_revision,
                    reverse_revision_attributes,
                )
                self._send(body, content_type, status=status)
                return
            if self._send_static_asset(path):
                return
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    return Handler


def _freshness_state(page: Any) -> str | None:
    return page.evaluate(
        """() => document.getElementById("templates-freshness-status")?.dataset.freshnessState ?? null"""
    )


def _wait_for_state(page: Any, state: str) -> None:
    page.wait_for_function(
        """expected => document.getElementById("templates-freshness-status")?.dataset.freshnessState === expected""",
        arg=state,
        timeout=10_000,
    )


def _wait_for_no_state(page: Any) -> None:
    page.wait_for_function(
        """() => document.getElementById("templates-freshness-status") === null""",
        timeout=10_000,
    )


def _wait_for_document_cache(page: Any, path: str = "/document/") -> None:
    page.wait_for_function(
        """async ([cacheName, path]) => {
          const cache = await caches.open(cacheName);
          return Boolean(await cache.match(path));
        }""",
        arg=[DOCUMENT_CACHE_NAME, path],
        timeout=5_000,
    )


def _wait_for_cached_document_text(
    page: Any,
    expected_text: str,
    path: str = "/document/",
) -> None:
    page.wait_for_function(
        """async ([cacheName, path, expectedText]) => {
          const cache = await caches.open(cacheName);
          const response = await cache.match(path);
          if (!response) return false;
          return (await response.text()).includes(expectedText);
        }""",
        arg=[DOCUMENT_CACHE_NAME, path, expected_text],
        timeout=10_000,
    )


def _fetch_html(page: Any, path: str) -> dict[str, Any]:
    result = page.evaluate(
        """async ([path, timeoutMs]) => await Promise.race([
          (async () => {
            const response = await fetch(path, { headers: { Accept: "text/html" } });
            return {
              status: response.status,
              freshness: response.headers.get("X-Templates-Freshness"),
              body: await response.text(),
            };
          })(),
          new Promise((resolve) => setTimeout(
            () => resolve({ timedOut: true, path }),
            timeoutMs
          )),
        ])""",
        [path, FETCH_CHECK_TIMEOUT_MS],
    )
    if result.get("timedOut"):
        raise PwaSlowConvergenceError(
            f"document fetch did not settle within {FETCH_CHECK_TIMEOUT_MS} ms: {path}"
        )
    return result


def _reload_from_status(page: Any) -> None:
    page.locator("#templates-freshness-status .freshness-status__reload").click()
    page.wait_for_load_state("load")


def _exercise_worker_epoch_reset(page: Any) -> None:
    result = page.evaluate(
        """async () => {
          const controller = navigator.serviceWorker.controller;
          if (!controller) return { priorApplied: false, resetApplied: false };
          const dispatchState = async (workerInstanceId, requestGeneration) => {
            const channel = new MessageChannel();
            return await new Promise((resolve) => {
              const timer = setTimeout(() => resolve(false), 2000);
              channel.port1.onmessage = (event) => {
                const data = event.data;
                clearTimeout(timer);
                resolve(
                  data?.type === "templates:freshness-state-applied" &&
                  data.state === "cached-unverified" &&
                  data.requestGeneration === requestGeneration &&
                  data.workerInstanceId === workerInstanceId
                );
              };
              navigator.serviceWorker.dispatchEvent(new MessageEvent("message", {
                data: {
                  type: "templates:freshness-state",
                  state: "cached-unverified",
                  url: window.location.href,
                  requestGeneration,
                  workerInstanceId,
                  awaitingCommit: true,
                },
                source: controller,
                ports: [channel.port2],
              }));
            });
          };
          const priorApplied = await dispatchState(
            "fixture-worker-instance-before-restart",
            9
          );
          const resetApplied = await dispatchState(
            "fixture-worker-instance-after-restart",
            1
          );
          return { priorApplied, resetApplied };
        }"""
    )
    if result != {"priorApplied": True, "resetApplied": True}:
        raise PwaSlowConvergenceError(
            f"worker-instance epoch did not reset request generation ordering: {result!r}"
        )
    _wait_for_state(page, "cached-unverified")


def _exercise_verified_current_commit_deferral(page: Any) -> None:
    state = page.evaluate(
        """async () => {
          const controller = navigator.serviceWorker.controller;
          if (!controller) return null;
          const workerInstanceId = "fixture-verified-current-deferral";
          const generation = 11;
          const channel = new MessageChannel();
          const applied = await new Promise((resolve) => {
            const timer = setTimeout(() => resolve(false), 2000);
            channel.port1.onmessage = (event) => {
              clearTimeout(timer);
              resolve(event.data?.type === "templates:freshness-state-applied");
            };
            navigator.serviceWorker.dispatchEvent(new MessageEvent("message", {
              data: {
                type: "templates:freshness-state",
                state: "checking",
                url: window.location.href,
                requestGeneration: generation,
                workerInstanceId,
                awaitingCommit: true,
              },
              source: controller,
              ports: [channel.port2],
            }));
          });
          if (!applied) return "ack-failed";
          navigator.serviceWorker.dispatchEvent(new MessageEvent("message", {
            data: {
              type: "templates:freshness-state",
              state: "verified-current",
              url: window.location.href,
              requestGeneration: generation,
              workerInstanceId,
              awaitingCommit: false,
            },
            source: controller,
          }));
          await new Promise((resolve) => setTimeout(resolve, 50));
          return document.getElementById("templates-freshness-status")?.dataset.freshnessState ?? null;
        }"""
    )
    if state != "checking":
        raise PwaSlowConvergenceError(
            f"verified-current cleared warning before cached commit: {state!r}"
        )
    page.evaluate("() => globalThis.__pwaFixtureCommitDocument('/document/')")
    _wait_for_no_state(page)


def _exercise_interrupted_commit_cleanup(page: Any) -> None:
    applied = page.evaluate(
        """async () => {
          const controller = navigator.serviceWorker.controller;
          if (!controller) return false;
          const channel = new MessageChannel();
          const workerInstanceId = "fixture-interrupted-commit";
          return await new Promise((resolve) => {
            const timer = setTimeout(() => resolve(false), 2000);
            channel.port1.onmessage = (event) => {
              clearTimeout(timer);
              resolve(event.data?.type === "templates:freshness-state-applied");
            };
            navigator.serviceWorker.dispatchEvent(new MessageEvent("message", {
              data: {
                type: "templates:freshness-state",
                state: "checking",
                url: window.location.href,
                requestGeneration: 13,
                workerInstanceId,
                awaitingCommit: true,
              },
              source: controller,
              ports: [channel.port2],
            }));
          });
        }"""
    )
    if applied is not True:
        raise PwaSlowConvergenceError("interrupted-commit setup was not acknowledged")
    _wait_for_state(page, "checking")
    page.evaluate("() => globalThis.__pwaFixtureCommitDocument('/interrupted/')")
    _wait_for_no_state(page)
    page.evaluate("() => history.replaceState({}, '', '/document/')")


def _exercise_controllerchange_missing_state_recovery(page: Any) -> None:
    applied = page.evaluate(
        """async () => {
          history.pushState({}, "", "/recovery-only/");
          const controller = navigator.serviceWorker.controller;
          if (!controller) return false;
          const channel = new MessageChannel();
          const workerInstanceId = "fixture-controllerchange-before-recovery";
          const acknowledged = await new Promise((resolve) => {
            const timer = setTimeout(() => resolve(false), 2000);
            channel.port1.onmessage = (event) => {
              clearTimeout(timer);
              resolve(event.data?.type === "templates:freshness-state-applied");
            };
            navigator.serviceWorker.dispatchEvent(new MessageEvent("message", {
              data: {
                type: "templates:freshness-state",
                state: "checking",
                url: window.location.href,
                requestGeneration: 15,
                workerInstanceId,
                awaitingCommit: true,
              },
              source: controller,
              ports: [channel.port2],
            }));
          });
          if (!acknowledged) return false;
          navigator.serviceWorker.dispatchEvent(new Event("controllerchange"));
          return true;
        }"""
    )
    if applied is not True:
        raise PwaSlowConvergenceError("controllerchange recovery setup failed")
    _wait_for_state(page, "cached-unverified")
    page.evaluate("() => history.replaceState({}, '', '/document/')")


def run_check(site_root: Path, output: Path | None) -> dict[str, Any]:
    try:
        required = check_pwa_capabilities._read_install_assets(site_root)
    except check_pwa_capabilities.PwaCapabilityError as exc:
        raise PwaSlowConvergenceError(str(exc)) from exc
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise PwaSlowConvergenceError(
            "built site is missing required PWA assets: "
            + ", ".join(path.as_posix() for path in missing)
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PwaSlowConvergenceError("Playwright is required for PWA convergence checks") from exc

    state = SlowFixtureState()
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

            page.goto(base_url + "/document/", wait_until="load")
            _wait_for_document_cache(page)
            if page.locator("#document-version").inner_text() != "document-v1":
                raise PwaSlowConvergenceError("initial document cache seed did not render v1")

            state.configure(
                version=9,
                revision="9" * 40,
                status=200,
                delay_ms=2200,
                content_type="text/html; charset=utf-8",
                include_revision=True,
                reverse_revision_attributes=False,
            )
            miss_started = time.monotonic()
            uncached = _fetch_html(page, "/uncached/")
            miss_elapsed = time.monotonic() - miss_started
            if uncached["status"] != 200 or "document-v9" not in uncached["body"]:
                raise PwaSlowConvergenceError(f"slow cache miss did not wait for network: {uncached!r}")
            if uncached["freshness"] is not None or miss_elapsed < 2.0:
                raise PwaSlowConvergenceError(
                    f"slow cache miss returned before network completion: {miss_elapsed:.3f}s"
                )
            evidence["cache_miss_waited_for_network"] = True

            state.configure(
                version=2,
                revision=REVISION_V2,
                delay_ms=2600,
                include_revision=True,
                reverse_revision_attributes=False,
            )
            changed_started = time.monotonic()
            changed = _fetch_html(page, "/document/")
            changed_elapsed = time.monotonic() - changed_started
            if changed["status"] != 200 or changed["freshness"] != "checking":
                raise PwaSlowConvergenceError(f"instant soft-timeout fallback was not checking: {changed!r}")
            if "document-v1" not in changed["body"] or not (1.2 <= changed_elapsed < 2.5):
                raise PwaSlowConvergenceError(
                    f"instant soft timeout did not reveal cached v1 near the configured boundary: {changed_elapsed:.3f}s"
                )
            if _freshness_state(page) != "checking":
                raise PwaSlowConvergenceError("instant navigation did not expose checking before cached content")
            _wait_for_state(page, "update-available")
            if page.locator("#document-version").inner_text() != "document-v1":
                raise PwaSlowConvergenceError("background convergence replaced visible DOM without reload")
            evidence["instant_checking"] = True
            evidence["instant_update_available"] = True

            state.configure(delay_ms=0)
            _reload_from_status(page)
            if page.locator("#document-version").inner_text() != "document-v2":
                raise PwaSlowConvergenceError("reload did not converge to verified v2")
            if _freshness_state(page) is not None:
                raise PwaSlowConvergenceError("verified v2 retained a freshness warning")

            state.configure(
                version=22,
                revision=REVISION_V2.upper(),
                delay_ms=2600,
                reverse_revision_attributes=True,
            )
            same_revision = _fetch_html(page, "/document/")
            if same_revision["freshness"] != "checking" or "document-v2" not in same_revision["body"]:
                raise PwaSlowConvergenceError("reordered revision-meta path did not begin in checking")
            _wait_for_cached_document_text(page, "document-v22")
            if _freshness_state(page) != "checking":
                raise PwaSlowConvergenceError(
                    "matching revision cleared checking before cached document commit"
                )
            page.evaluate("() => globalThis.__pwaFixtureCommitDocument('/document/')")
            _wait_for_no_state(page)
            evidence["reordered_meta_verified_current"] = True

            state.configure(
                version=3,
                revision=REVISION_V3,
                delay_ms=2600,
                include_revision=False,
                reverse_revision_attributes=False,
            )
            missing_revision = _fetch_html(page, "/document/")
            if missing_revision["freshness"] != "checking":
                raise PwaSlowConvergenceError("missing-revision response did not expose checking first")
            _wait_for_state(page, "update-available")
            evidence["missing_revision_update_available"] = True

            state.configure(
                version=3,
                revision=REVISION_V3,
                delay_ms=0,
                include_revision=True,
                content_type="text/html; charset=utf-8",
            )
            _reload_from_status(page)
            if page.locator("#document-version").inner_text() != "document-v3":
                raise PwaSlowConvergenceError("reload did not seed verified v3")

            state.configure(
                delay_ms=2600,
                content_type="application/json; charset=utf-8",
            )
            non_html = _fetch_html(page, "/document/")
            if non_html["freshness"] != "checking":
                raise PwaSlowConvergenceError("non-HTML 200 did not expose checking cached content")
            _wait_for_state(page, "update-available")
            evidence["non_html_update_available"] = True

            state.configure(
                status=503,
                delay_ms=2600,
                content_type="text/html; charset=utf-8",
                include_revision=True,
            )
            slow_failure = _fetch_html(page, "/document/")
            if slow_failure["freshness"] != "checking":
                raise PwaSlowConvergenceError("slow 5xx path did not begin in checking state")
            _wait_for_state(page, "cached-unverified")
            evidence["slow_failure_cached_unverified"] = True

            state.configure(
                version=4,
                revision=REVISION_V4,
                status=200,
                delay_ms=2600,
                content_type="text/html; charset=utf-8",
                include_revision=True,
                reverse_revision_attributes=False,
            )
            direct_page = context.new_page()
            direct_started = time.monotonic()
            response = direct_page.goto(
                base_url + "/document/",
                wait_until="domcontentloaded",
                timeout=10_000,
            )
            direct_elapsed = time.monotonic() - direct_started
            if response is None or response.status != 200:
                status = None if response is None else response.status
                raise PwaSlowConvergenceError(
                    f"direct full navigation returned {status}, expected cached 200"
                )
            if direct_page.locator("#document-version").inner_text() != "document-v3":
                raise PwaSlowConvergenceError("direct full navigation did not reveal cached v3")
            if _freshness_state(direct_page) != "checking" or direct_elapsed >= 2.5:
                raise PwaSlowConvergenceError(
                    "full navigation incorrectly waited for UI acknowledgement or network completion"
                )
            _wait_for_state(direct_page, "update-available")
            if direct_page.locator("#document-version").inner_text() != "document-v3":
                raise PwaSlowConvergenceError("full-navigation convergence replaced visible DOM")
            evidence["full_navigation_without_preexisting_client_ack"] = True
            evidence["full_navigation_update_available"] = True
            direct_page.close()

            state.configure(
                version=4,
                revision=REVISION_V4,
                status=200,
                delay_ms=0,
                content_type="text/html; charset=utf-8",
                include_revision=True,
                reverse_revision_attributes=False,
            )
            page.reload(wait_until="load", timeout=10_000)
            _wait_for_no_state(page)
            if page.locator("#document-version").inner_text() != "document-v4":
                raise PwaSlowConvergenceError("race-regression setup did not render v4")

            _exercise_verified_current_commit_deferral(page)
            evidence["verified_current_waited_for_cached_commit"] = True
            page.reload(wait_until="load", timeout=10_000)
            _wait_for_no_state(page)

            _exercise_interrupted_commit_cleanup(page)
            evidence["interrupted_commit_warning_cleared"] = True
            page.reload(wait_until="load", timeout=10_000)
            _wait_for_no_state(page)

            _exercise_controllerchange_missing_state_recovery(page)
            evidence["controllerchange_missing_state_downgraded"] = True
            page.reload(wait_until="load", timeout=10_000)
            _wait_for_no_state(page)

            _exercise_worker_epoch_reset(page)
            evidence["worker_restart_generation_reset"] = True
            page.reload(wait_until="load", timeout=10_000)
            _wait_for_no_state(page)

            state.configure(
                version=5,
                revision=REVISION_V5,
                delay_ms=2600,
            )
            older_same_url = _fetch_html(page, "/document/")
            if older_same_url["freshness"] != "checking":
                raise PwaSlowConvergenceError("same-URL ordering setup did not enter checking")
            state.configure(
                version=6,
                revision=REVISION_V6,
                delay_ms=0,
            )
            newer_same_url = _fetch_html(page, "/document/")
            if newer_same_url["status"] != 200 or "document-v6" not in newer_same_url["body"]:
                raise PwaSlowConvergenceError("newer same-URL response did not complete from network")
            page.evaluate("() => globalThis.__pwaFixtureCommitDocument('/document/')")
            _wait_for_no_state(page)
            page.wait_for_timeout(1600)
            if _freshness_state(page) is not None:
                raise PwaSlowConvergenceError(
                    "older same-URL convergence overrode the newer committed representation"
                )
            evidence["newer_commit_retired_old_convergence"] = True

            state.configure(
                version=7,
                revision=REVISION_V7,
                delay_ms=2600,
            )
            previous_document = _fetch_html(page, "/document/")
            if previous_document["freshness"] != "checking":
                raise PwaSlowConvergenceError("previous-document ordering setup did not enter checking")
            page.evaluate("() => globalThis.__pwaFixtureCommitDocument('/')")
            _wait_for_no_state(page)
            page.wait_for_timeout(1600)
            if _freshness_state(page) is not None:
                raise PwaSlowConvergenceError(
                    "late convergence from the previous document mutated the current page"
                )
            evidence["previous_document_convergence_ignored"] = True
            evidence["document_hits"] = state.document_hits
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