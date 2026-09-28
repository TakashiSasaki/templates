#!/usr/bin/env python3
"""Exercise generated translation warnings through navigation and real PWA cache."""

from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import argparse
import json
import sys
import threading
import time
import traceback

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publication_bundle.paths import public_path
from site_renderer.bundle import load_lock, validate_locked


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log(event):
    print(
        "SITE_PWA_DIAGNOSTIC "
        + json.dumps(event, ensure_ascii=False, sort_keys=True),
        flush=True,
    )


@contextmanager
def _phase(evidence, name):
    started = time.monotonic()
    record = {"name": name, "started_at": _utc_now(), "status": "running"}
    evidence["phases"].append(record)
    _log({"kind": "phase", **record})
    try:
        yield
    except BaseException as exc:
        record.update(
            status="failed",
            ended_at=_utc_now(),
            duration_seconds=round(time.monotonic() - started, 3),
            error_type=type(exc).__name__,
            error=str(exc),
        )
        _log({"kind": "phase", **record})
        raise
    else:
        record.update(
            status="passed",
            ended_at=_utc_now(),
            duration_seconds=round(time.monotonic() - started, 3),
        )
        _log({"kind": "phase", **record})


def _diagnostic_error(evidence, operation, exc):
    record = {
        "operation": operation,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }
    evidence["diagnostic_errors"].append(record)
    _log({"kind": "diagnostic_error", **record})


# Injected only by this check's local server; it is not part of the Pages artifact.
_SERVICE_WORKER_DIAGNOSTIC_PRELUDE = r"""const SITE_PWA_DIAGNOSTIC_ROLLOUT = __SITE_PWA_DIAGNOSTIC_ROLLOUT__;
(() => {
  const observedTypes = new Set(["activate", "fetch", "install", "message"]);
  const addEventListener = self.addEventListener.bind(self);
  let eventSequence = 0;
  let promiseSequence = 0;

  const requestSkipWaiting = self.skipWaiting.bind(self);
  self.skipWaiting = function() {
    const promiseId = ++promiseSequence;
    const startedAt = performance.now();
    const log = (stage, extra = {}) => {
      try {
        console.debug("SITE_PWA_SW_EVENT " + JSON.stringify({
          rollout: SITE_PWA_DIAGNOSTIC_ROLLOUT,
          event_id: "skipWaiting-" + promiseId,
          event_type: "skipWaiting",
          stage,
          worker_elapsed_ms: Math.round(performance.now() * 10) / 10,
          ...extra,
        }));
      } catch (_) {}
    };

    log("skipWaiting_called", {promise_id: promiseId});
    let promise;
    try {
      promise = requestSkipWaiting();
    } catch (error) {
      log("skipWaiting_threw", {
        error_name: String(error?.name || "Error"),
        error_message: String(error?.message || error).slice(0, 1000),
      });
      throw error;
    }
    return Promise.resolve(promise).then(
      value => {
        log("skipWaiting_fulfilled", {
          promise_id: promiseId,
          duration_ms: Math.round((performance.now() - startedAt) * 10) / 10,
        });
        return value;
      },
      error => {
        log("skipWaiting_rejected", {
          promise_id: promiseId,
          duration_ms: Math.round((performance.now() - startedAt) * 10) / 10,
          error_name: String(error?.name || "Error"),
          error_message: String(error?.message || error).slice(0, 1000),
        });
        throw error;
      },
    );
  };

  self.addEventListener = function(type, listener, options) {
    if (!observedTypes.has(type) || typeof listener !== "function") {
      return addEventListener(type, listener, options);
    }

    const observedListener = function(event) {
      const eventId = ++eventSequence;
      const request = event.request || null;
      const log = (stage, extra = {}) => {
        const observation = {
          rollout: SITE_PWA_DIAGNOSTIC_ROLLOUT,
          event_id: eventId,
          event_type: type,
          stage,
          worker_elapsed_ms: Math.round(performance.now() * 10) / 10,
          ...extra,
        };
        if (request) {
          observation.request_method = request.method;
          observation.request_url = request.url;
          observation.request_mode = request.mode;
          observation.request_destination = request.destination;
        }
        try {
          console.debug("SITE_PWA_SW_EVENT " + JSON.stringify(observation));
        } catch (_) {}
      };
      const trackPromise = (method, promise) => {
        const promiseId = ++promiseSequence;
        const startedAt = performance.now();
        log(method + "_pending", {promise_id: promiseId});
        return Promise.resolve(promise).then(
          value => {
            log(method + "_fulfilled", {
              promise_id: promiseId,
              duration_ms: Math.round((performance.now() - startedAt) * 10) / 10,
            });
            return value;
          },
          error => {
            log(method + "_rejected", {
              promise_id: promiseId,
              duration_ms: Math.round((performance.now() - startedAt) * 10) / 10,
              error_name: String(error?.name || "Error"),
              error_message: String(error?.message || error).slice(0, 1000),
            });
            throw error;
          },
        );
      };

      log("dispatched");
      for (const method of ["waitUntil", "respondWith"]) {
        if (typeof event[method] !== "function") continue;
        const originalMethod = event[method].bind(event);
        event[method] = promise => originalMethod(trackPromise(method, promise));
      }
      try {
        const result = listener.call(this, event);
        log("handler_returned");
        return result;
      } catch (error) {
        log("handler_threw", {
          error_name: String(error?.name || "Error"),
          error_message: String(error?.message || error).slice(0, 1000),
        });
        throw error;
      }
    };

    return addEventListener(type, observedListener, options);
  };
})();
"""


def _service_worker_diagnostic_prelude(rollout):
    return _SERVICE_WORKER_DIAGNOSTIC_PRELUDE.replace(
        "__SITE_PWA_DIAGNOSTIC_ROLLOUT__", str(rollout)
    ).encode("utf-8")


def _attach_browser_diagnostics(context, page, evidence, run_started):
    requests = {}

    def event(kind, **details):
        record = {
            "kind": kind,
            "elapsed_seconds": round(time.monotonic() - run_started, 3),
            **details,
        }
        evidence["browser_events"].append(record)
        _log(record)

    def on_request(request):
        now = time.monotonic()
        try:
            service_worker = request.service_worker
        except Exception:
            service_worker = None
        record = {
            "method": request.method,
            "url": request.url,
            "resource_type": request.resource_type,
            "initiator": "service_worker" if service_worker else "browser",
            "service_worker_url": service_worker.url if service_worker else None,
            "started_elapsed_seconds": round(now - run_started, 3),
            "status": None,
            "response_elapsed_seconds": None,
            "duration_seconds": None,
            "failure": None,
        }
        requests[id(request)] = (now, record)
        evidence["network_requests"].append(record)
        event(
            "browser_request",
            method=record["method"],
            url=record["url"],
            resource_type=record["resource_type"],
            initiator=record["initiator"],
            service_worker_url=record["service_worker_url"],
        )

    def on_response(response):
        request = response.request
        started, record = requests.get(id(request), (time.monotonic(), None))
        if record is not None:
            record["status"] = response.status
            record["response_elapsed_seconds"] = round(
                time.monotonic() - run_started, 3
            )
        event(
            "browser_response",
            method=request.method,
            url=response.url,
            status=response.status,
            request_elapsed_seconds=round(time.monotonic() - started, 3),
        )

    def on_request_finished(request):
        started, record = requests.pop(
            id(request), (time.monotonic(), None)
        )
        duration = round(time.monotonic() - started, 3)
        if record is not None:
            record["duration_seconds"] = duration
        event(
            "browser_request_finished",
            method=request.method,
            url=request.url,
            duration_seconds=duration,
        )

    def on_request_failed(request):
        started, record = requests.pop(
            id(request), (time.monotonic(), None)
        )
        duration = round(time.monotonic() - started, 3)
        failure = request.failure
        if record is not None:
            record["duration_seconds"] = duration
            record["failure"] = failure
        event(
            "browser_request_failed",
            method=request.method,
            url=request.url,
            duration_seconds=duration,
            failure=failure,
        )

    context.on("request", on_request)
    context.on("response", on_response)
    context.on("requestfinished", on_request_finished)
    context.on("requestfailed", on_request_failed)
    def on_service_worker(worker):
        event("service_worker", url=worker.url)

        def on_worker_console(message):
            prefix = "SITE_PWA_SW_EVENT "
            if message.text.startswith(prefix):
                try:
                    observation = json.loads(message.text[len(prefix) :])
                except json.JSONDecodeError as exc:
                    event(
                        "service_worker_event_lifecycle_parse_error",
                        url=worker.url,
                        text=message.text,
                        error=str(exc),
                    )
                else:
                    event(
                        "service_worker_event_lifecycle",
                        url=worker.url,
                        observation=observation,
                    )
            elif message.type in ("warning", "error"):
                event(
                    "service_worker_console",
                    url=worker.url,
                    message_type=message.type,
                    text=message.text,
                )

        worker.on("console", on_worker_console)

    context.on("serviceworker", on_service_worker)
    def on_console(message):
        prefix = "SITE_PWA_SW_UPDATE "
        if message.text.startswith(prefix):
            try:
                observation = json.loads(message.text[len(prefix) :])
            except json.JSONDecodeError as exc:
                event(
                    "service_worker_update_lifecycle_parse_error",
                    text=message.text,
                    error=str(exc),
                )
            else:
                event(
                    "service_worker_update_lifecycle",
                    observation=observation,
                )
        elif message.type in ("warning", "error"):
            event(
                "browser_console",
                message_type=message.type,
                text=message.text,
            )

    page.on("console", on_console)
    page.on(
        "pageerror",
        lambda error: event("browser_page_error", error=str(error)),
    )


def _run_phase(evidence, name, action):
    with _phase(evidence, name):
        return action()


def _start_service_worker_update_probe(page):
    return page.evaluate(
        """async () => {
            const key = "__sitePwaUpdateProbe";
            const registration = await navigator.serviceWorker.ready;
            const startedAt = performance.now();
            const workerSummary = worker => worker ? {
                script_url: worker.scriptURL,
                state: worker.state,
            } : null;
            const registrationSummary = () => ({
                active: workerSummary(registration.active),
                waiting: workerSummary(registration.waiting),
                installing: workerSummary(registration.installing),
                controller: workerSummary(navigator.serviceWorker.controller),
            });
            const probe = {
                started_at: startedAt,
                update_status: "pending",
                update_error: null,
                controller_changed: false,
                events: [],
            };
            const record = (name, details = {}) => {
                const observation = {
                    name,
                    elapsed_ms: Math.round((performance.now() - startedAt) * 10) / 10,
                    ...details,
                };
                probe.events.push(observation);
                console.debug("SITE_PWA_SW_UPDATE " + JSON.stringify(observation));
            };
            const recordWorkerState = worker => {
                if (!worker) return;
                record("worker_state_observed", {worker: workerSummary(worker)});
                worker.addEventListener("statechange", () => {
                    record("worker_statechange", {worker: workerSummary(worker)});
                });
            };
            const snapshot = () => ({
                update_status: probe.update_status,
                update_error: probe.update_error,
                controller_changed: probe.controller_changed,
                events: [...probe.events],
                registration: registrationSummary(),
            });

            window[key] = probe;
            record("registration_ready", {registration: registrationSummary()});
            recordWorkerState(registration.installing);
            registration.addEventListener("updatefound", () => {
                const installing = registration.installing;
                record("updatefound", {registration: registrationSummary()});
                recordWorkerState(installing);
            });
            navigator.serviceWorker.addEventListener("controllerchange", () => {
                probe.controller_changed = true;
                record("controllerchange", {registration: registrationSummary()});
            }, {once: true});

            let updatePromise;
            try {
                updatePromise = registration.update();
            } catch (error) {
                probe.update_status = "rejected";
                probe.update_error = {name: error.name, message: error.message};
                record("registration_update_rejected", {
                    error: probe.update_error,
                    registration: registrationSummary(),
                });
                return {started: true, initial: snapshot()};
            }
            record("registration_update_started", {registration: registrationSummary()});
            Promise.resolve(updatePromise).then(() => {
                probe.update_status = "fulfilled";
                record("registration_update_fulfilled", {registration: registrationSummary()});
            }, error => {
                probe.update_status = "rejected";
                probe.update_error = {name: error.name, message: error.message};
                record("registration_update_rejected", {
                    error: probe.update_error,
                    registration: registrationSummary(),
                });
            });
            return {started: true, initial: snapshot()};
        }"""
    )


def _capture_service_worker_update_probe(page):
    return page.evaluate(
        """async () => {
            const probe = window.__sitePwaUpdateProbe;
            if (!probe) return null;
            const registration = await navigator.serviceWorker.ready;
            const workerSummary = worker => worker ? {
                script_url: worker.scriptURL,
                state: worker.state,
            } : null;
            return {
                update_status: probe.update_status,
                update_error: probe.update_error,
                controller_changed: probe.controller_changed,
                events: [...probe.events],
                registration: {
                    active: workerSummary(registration.active),
                    waiting: workerSummary(registration.waiting),
                    installing: workerSummary(registration.installing),
                },
                controller: workerSummary(navigator.serviceWorker.controller),
            };
        }"""
    )


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def run(site, bundle, output=None):
    run_started = time.monotonic()
    evidence = {
        "status": "running",
        "started_at": _utc_now(),
        "phases": [],
        "browser_events": [],
        "network_requests": [],
        "server_requests": [],
        "diagnostic_errors": [],
        "checks": [],
    }
    trace_path = (
        output.with_name("translation-runtime-trace.zip") if output else None
    )
    evidence["trace"] = {
        "status": "not_requested" if trace_path is None else "pending",
        "path": trace_path.name if trace_path else None,
    }
    server = None
    thread = None
    server_started = False
    playwright = None
    browser = None
    context = None
    page = None
    trace_started = False
    server_event_lock = threading.Lock()

    try:
        with _phase(evidence, "bundle.validate"):
            lock = load_lock(Path(__file__).resolve().parents[1] / "integration-source.json")
            identity = validate_locked(bundle, lock)
            evidence.update(
                integration=identity["producer"]["revision"],
                bundle_identity=identity["identity"],
            )
            records = json.loads(
                (bundle / "translation-availability.json").read_text()
            )["records"]
            stale = next(
                r
                for r in records
                if r["status"] == "stale" and r["language"] == "ja"
            )
            current = next(
                r
                for r in records
                if r["status"] == "current" and r["language"] == "ja"
            )
            missing = next(
                r
                for r in records
                if r["status"] == "missing" and r["language"] == "ja"
            )
            stale_route = public_path("ja/" + stale["canonical_destination"])
            current_route = public_path("ja/" + current["canonical_destination"])
            missing_route = public_path("ja/" + missing["canonical_destination"])
            canonical_route = public_path(stale["canonical_destination"])
            evidence.update(
                stale_route=stale_route,
                current_route=current_route,
                missing_route=missing_route,
                canonical_route=canonical_route,
            )
            assert not (site / missing_route.lstrip("/") / "index.html").exists(), (
                "missing translation route fabricated"
            )

        state = {"worker": 1, "delay": 0}
        base_holder = {}

        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def log_request(self, code="-", size="-"):
                self._diagnostic_status = code

            def do_GET(self):
                started = time.monotonic()
                self._diagnostic_status = None
                error = None
                try:
                    self._handle_get()
                except BaseException as exc:
                    error = {"type": type(exc).__name__, "message": str(exc)}
                    raise
                finally:
                    record = {
                        "method": "GET",
                        "path": urlsplit(self.path).path,
                        "status": self._diagnostic_status,
                        "duration_seconds": round(time.monotonic() - started, 3),
                    }
                    if error is not None:
                        record["error"] = error
                    with server_event_lock:
                        evidence["server_requests"].append(record)
                    _log({"kind": "server_request", **record})

            def _handle_get(self):
                path = urlsplit(self.path).path
                if path == stale_route and state["delay"]:
                    time.sleep(state["delay"])
                if path == "/service-worker.js":
                    body = _service_worker_diagnostic_prelude(
                        state["worker"]
                    ) + (site / "service-worker.js").read_bytes() + (
                        f"\n// acceptance rollout {state['worker']}\n".encode()
                    )
                    self.send_response(200)
                    self.send_header("Content-Type", "text/javascript")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                # Serve the same artifact under a loopback origin; only anchor origins
                # change so real language links remain inside the test deployment.
                relative = path.lstrip("/") + ("index.html" if path.endswith("/") else "")
                candidate = (site / relative).resolve()
                if (
                    candidate.is_relative_to(site.resolve())
                    and candidate.is_file()
                    and candidate.suffix == ".html"
                ):
                    body = candidate.read_text().replace(
                        'href="https://templates.moukaeritai.work/',
                        'href="' + base_holder["base"] + "/",
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                super().do_GET()

        with _phase(evidence, "http_server.start"):
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0), partial(Handler, directory=str(site))
            )
            base = f"http://127.0.0.1:{server.server_port}"
            base_holder["base"] = base
            evidence["origin"] = base
            thread = threading.Thread(
                target=server.serve_forever, daemon=True
            )
            thread.start()
            server_started = True

        with _phase(evidence, "playwright.controller.start"):
            from playwright.sync_api import sync_playwright

            playwright = sync_playwright().start()

        with _phase(evidence, "browser.launch.system_chrome"):
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            evidence["browser_version"] = browser.version

        with _phase(evidence, "browser.context.create"):
            context = browser.new_context(viewport={"width": 390, "height": 844})

        with _phase(evidence, "browser.page.create"):
            page = context.new_page()

        _attach_browser_diagnostics(context, page, evidence, run_started)

        if trace_path is not None:
            with _phase(evidence, "browser.trace.start"):
                trace_path.parent.mkdir(parents=True, exist_ok=True)
                context.tracing.start(
                    screenshots=False,
                    snapshots=True,
                    sources=False,
                )
                trace_started = True
                evidence["trace"]["status"] = "recording"

        def warning(label):
            with _phase(evidence, "assert_warning." + label):
                box = page.locator(".translation-stale-warning")
                box.wait_for(state="visible")
                assert box.count() == 1 and box.get_attribute("role") == "note"
                assert (
                    box.get_attribute("aria-labelledby")
                    == "translation-stale-title"
                )
                assert "非正本" in box.inner_text() and "英語正本が変更" in box.inner_text()
                assert (
                    urlsplit(box.locator("a").get_attribute("href")).path
                    == canonical_route
                )
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth + 1"
                ), "warning causes horizontal overflow"
                evidence["checks"].append(label)

        _run_phase(
            evidence,
            "navigation.initial_stale.wait_networkidle",
            lambda: page.goto(base + stale_route, wait_until="networkidle"),
        )
        warning("online")
        _run_phase(
            evidence,
            "service_worker.wait_for_controller",
            lambda: page.wait_for_function(
                "navigator.serviceWorker.controller !== null", timeout=30000
            ),
        )
        _run_phase(
            evidence,
            "navigation.reload_stale.wait_networkidle",
            lambda: page.reload(wait_until="networkidle"),
        )
        warning("reload")
        _run_phase(
            evidence,
            "navigation.language_switch_to_english.click",
            lambda: page.locator(
                '.translation-switcher a[hreflang="en"]'
            ).click(),
        )
        _run_phase(
            evidence,
            "navigation.language_switch_to_english.wait_for_url",
            lambda: page.wait_for_url(base + canonical_route),
        )
        _run_phase(
            evidence,
            "assert_warning.absent_on_canonical_english",
            lambda: _assert(
                page.locator(".translation-stale-warning").count() == 0,
                "stale warning on canonical route",
            ),
        )
        _run_phase(
            evidence,
            "navigation.language_switch_to_japanese.click",
            lambda: page.locator(
                '.translation-switcher a[hreflang="ja"]'
            ).click(),
        )
        _run_phase(
            evidence,
            "navigation.language_switch_to_japanese.wait_for_url",
            lambda: page.wait_for_url(base + stale_route),
        )
        warning("language-switch")
        _run_phase(evidence, "navigation.history.back", page.go_back)
        _run_phase(
            evidence,
            "navigation.history.back.wait_for_url",
            lambda: page.wait_for_url(base + canonical_route),
        )
        _run_phase(evidence, "navigation.history.forward", page.go_forward)
        _run_phase(
            evidence,
            "navigation.history.forward.wait_for_url",
            lambda: page.wait_for_url(base + stale_route),
        )
        warning("back-forward")

        _run_phase(
            evidence,
            "navigation.current_translation.wait_networkidle",
            lambda: page.goto(base + current_route, wait_until="networkidle"),
        )
        _run_phase(
            evidence,
            "assert_warning.absent_on_current_translation",
            lambda: _assert(
                page.locator(".translation-stale-warning").count() == 0,
                "stale warning on current route",
            ),
        )
        _run_phase(
            evidence,
            "assert.language_switcher_on_current_translation",
            lambda: _assert(
                page.locator(".translation-switcher").count() == 1,
                "translation switcher missing",
            ),
        )
        evidence["checks"].append("current-without-warning")

        _run_phase(
            evidence,
            "navigation.return_to_stale.wait_networkidle",
            lambda: page.goto(base + stale_route, wait_until="networkidle"),
        )
        warning("return-to-stale")
        _run_phase(
            evidence,
            "service_worker.wait_for_cached_stale_document",
            lambda: page.wait_for_function(
                """async route => {
                    const cache = await caches.open('templates-portal-documents-v1');
                    return !!(await cache.match(new URL(route, location.origin).href));
                }""",
                arg=stale_route,
                timeout=30000,
            ),
        )
        _run_phase(
            evidence,
            "network.set_offline.before_cached_reload",
            lambda: context.set_offline(True),
        )
        _run_phase(
            evidence,
            "navigation.offline_cached_reload.domcontentloaded",
            lambda: page.reload(wait_until="domcontentloaded"),
        )
        warning("offline-cached-reload")
        _run_phase(
            evidence,
            "network.set_online.before_worker_update",
            lambda: context.set_offline(False),
        )
        _run_phase(
            evidence,
            "state.set_worker_rollout_2",
            lambda: state.update(worker=2),
        )
        probe_start = _run_phase(
            evidence,
            "service_worker.update_probe.start",
            lambda: _start_service_worker_update_probe(page),
        )
        evidence["service_worker_update_probe_start"] = probe_start
        _run_phase(
            evidence,
            "service_worker.wait_for_update_settlement_or_controllerchange",
            lambda: page.wait_for_function(
                """() => {
                    const probe = window.__sitePwaUpdateProbe;
                    return probe && (
                        probe.update_status !== "pending" || probe.controller_changed
                    );
                }""",
                timeout=0,
            ),
        )
        _run_phase(
            evidence,
            "service_worker.wait_for_controllerchange",
            lambda: page.wait_for_function(
                "window.__sitePwaUpdateProbe?.controller_changed === true",
                timeout=0,
            ),
        )
        update_snapshot = _run_phase(
            evidence,
            "service_worker.capture_update_lifecycle",
            lambda: _capture_service_worker_update_probe(page),
        )
        _assert(
            update_snapshot is not None,
            "service worker update probe disappeared before capture",
        )
        evidence["service_worker_update"] = update_snapshot
        _log({"kind": "service_worker_update_snapshot", **update_snapshot})
        _run_phase(
            evidence,
            "navigation.after_worker_update.wait_networkidle",
            lambda: page.reload(wait_until="networkidle"),
        )
        warning("worker-update")

        _run_phase(
            evidence,
            "state.set_slow_network_delay",
            lambda: state.update(delay=1.0),
        )
        _run_phase(
            evidence,
            "navigation.slow_network_convergence.domcontentloaded",
            lambda: page.reload(wait_until="domcontentloaded"),
        )
        warning("slow-network-convergence")
        _run_phase(
            evidence,
            "network.set_offline.after_worker_update",
            lambda: context.set_offline(True),
        )
        _run_phase(
            evidence,
            "navigation.offline_after_worker_update.domcontentloaded",
            lambda: page.reload(wait_until="domcontentloaded"),
        )
        warning("offline-after-worker-update")
        _run_phase(
            evidence,
            "network.restore_online_before_cleanup",
            lambda: context.set_offline(False),
        )
    except BaseException as exc:
        evidence["status"] = "failed"
        evidence["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        raise
    finally:
        if page is not None and "service_worker_update" not in evidence:
            try:
                partial_probe = _capture_service_worker_update_probe(page)
                if partial_probe is not None:
                    evidence["service_worker_update"] = partial_probe
                    _log(
                        {
                            "kind": "service_worker_update_snapshot",
                            "partial": True,
                            **partial_probe,
                        }
                    )
            except Exception as exc:
                _diagnostic_error(
                    evidence,
                    "service_worker.update_probe.capture_partial",
                    exc,
                )
        if trace_started and context is not None:
            try:
                with _phase(evidence, "browser.trace.stop"):
                    context.tracing.stop(path=str(trace_path))
                evidence["trace"]["status"] = "saved"
            except Exception as exc:
                evidence["trace"]["status"] = "failed"
                _diagnostic_error(evidence, "browser.trace.stop", exc)
        if browser is not None:
            try:
                with _phase(evidence, "browser.close"):
                    browser.close()
            except Exception as exc:
                _diagnostic_error(evidence, "browser.close", exc)
        if playwright is not None:
            try:
                with _phase(evidence, "playwright.controller.stop"):
                    playwright.stop()
            except Exception as exc:
                _diagnostic_error(evidence, "playwright.controller.stop", exc)
        if server is not None:
            try:
                with _phase(evidence, "http_server.stop"):
                    if server_started:
                        server.shutdown()
                    server.server_close()
                    if server_started and thread is not None:
                        thread.join(timeout=5)
                        if thread.is_alive():
                            raise RuntimeError("local HTTP server thread did not stop")
            except Exception as exc:
                _diagnostic_error(evidence, "http_server.stop", exc)
        if evidence["status"] == "running":
            evidence["status"] = "passed"
        evidence["ended_at"] = _utc_now()
        evidence["duration_seconds"] = round(time.monotonic() - run_started, 3)
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
        _log(
            {
                "kind": "result",
                "status": evidence["status"],
                "duration_seconds": evidence["duration_seconds"],
                "completed_checks": evidence["checks"],
                "phase_count": len(evidence["phases"]),
                "network_request_count": len(evidence["network_requests"]),
                "server_request_count": len(evidence["server_requests"]),
                "trace_status": evidence["trace"]["status"],
            }
        )

    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.site_root.resolve(), args.bundle.resolve(), args.output)
    # Keep the existing concise stdout JSON contract; detailed evidence is written
    # to --output and emitted as individual SITE_PWA_DIAGNOSTIC log records.
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "integration",
                    "bundle_identity",
                    "stale_route",
                    "current_route",
                    "missing_route",
                    "checks",
                )
            }
        )
    )
