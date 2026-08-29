from __future__ import annotations

import base64
import json
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BROWSER_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "webapp_browser"
if str(BROWSER_FIXTURE_DIR) not in sys.path:
    sys.path.insert(0, str(BROWSER_FIXTURE_DIR))

from browser_probe import _open_webdriver_session  # noqa: E402

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z9WQAAAAASUVORK5CYII="
)
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect width="16" height="16" rx="3"/></svg>'

APP_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" sizes="any">
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180">
  <title>PWA evidence fixture</title>
</head>
<body data-state="booting" data-current="false" data-active-revision="1">
  <main id="shell">
    <p id="status">Starting</p>
    <p id="value"></p>
    <button id="retry" type="button" onclick="refreshData()">Retry</button>
    <button id="check-update" type="button" onclick="checkUpdate()">Check update</button>
    <button id="apply-update" type="button" onclick="applyUpdate()">Apply update</button>
  </main>
<script>
let activeRevision = '1';
let availableRevision = null;
function setState(state, message, value, current) {
  document.body.dataset.state = state;
  document.body.dataset.current = current ? 'true' : 'false';
  document.body.dataset.activeRevision = activeRevision;
  document.getElementById('status').textContent = message;
  document.getElementById('value').textContent = value || '';
}
async function refreshData() {
  const cached = localStorage.getItem('cached-data');
  setState('revalidating', 'Checking authoritative source', cached ? JSON.parse(cached).value : '', false);
  try {
    const response = await fetch('/data?ts=' + Date.now(), {cache: 'no-store'});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const payload = await response.json();
    localStorage.setItem('cached-data', JSON.stringify(payload));
    setState('current', 'Current after authoritative revalidation', payload.value, true);
  } catch (error) {
    if (cached) {
      const payload = JSON.parse(cached);
      setState('freshness-unverified', 'Offline: freshness unverified', payload.value, false);
    } else {
      setState('offline-unavailable', 'Offline: current data unavailable', '', false);
    }
  }
}
async function checkUpdate() {
  setState('update-checking', 'Checking application update', document.getElementById('value').textContent, false);
  try {
    const response = await fetch('/app-revision?ts=' + Date.now(), {cache: 'no-store'});
    const payload = await response.json();
    if (payload.revision !== activeRevision) {
      availableRevision = payload.revision;
      setState('update-available', 'Application update available', document.getElementById('value').textContent, false);
    } else {
      setState('update-current', 'Application is current', document.getElementById('value').textContent, true);
    }
  } catch (error) {
    setState('update-check-failed', 'Unable to verify application update', document.getElementById('value').textContent, false);
  }
}
function applyUpdate() {
  if (!availableRevision) return;
  setState('update-applying', 'Applying application update', document.getElementById('value').textContent, false);
  window.setTimeout(() => {
    activeRevision = availableRevision;
    availableRevision = null;
    setState('update-applied', 'Application update applied', document.getElementById('value').textContent, true);
  }, 50);
}
window.refreshData = refreshData;
window.checkUpdate = checkUpdate;
window.applyUpdate = applyUpdate;
window.addEventListener('DOMContentLoaded', refreshData);
</script>
</body>
</html>
"""


class OriginState:
    def __init__(self) -> None:
        self.data_revision = 1
        self.app_revision = 1
        self.data_delay = 0.0


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "PwaEvidenceFixture/1"

    @property
    def state(self) -> OriginState:
        return self.server.fixture_state  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        return

    def respond(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in {"/app", "/app/"}:
            self.respond(200, "text/html; charset=utf-8", APP_HTML.encode("utf-8"))
            return
        if path == "/manifest.webmanifest":
            manifest = {
                "name": "PWA evidence fixture",
                "short_name": "PWA fixture",
                "start_url": "/app",
                "scope": "/app/",
                "display": "standalone",
                "icons": [
                    {"src": "/app-icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
                    {"src": "/app-icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                    {"src": "/app-icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
                ],
            }
            self.respond(200, "application/manifest+json", json.dumps(manifest).encode("utf-8"))
            return
        if path in {"/favicon.svg", "/app-icon.svg"}:
            self.respond(200, "image/svg+xml", SVG)
            return
        if path in {"/apple-touch-icon.png", "/app-icon-192.png", "/app-icon-512.png"}:
            self.respond(200, "image/png", PNG_1X1)
            return
        if path == "/data":
            if self.state.data_delay:
                time.sleep(self.state.data_delay)
            payload = {
                "revision": self.state.data_revision,
                "value": f"revision-{self.state.data_revision}",
            }
            self.respond(200, "application/json", json.dumps(payload).encode("utf-8"))
            return
        if path == "/app-revision":
            payload = {"revision": str(self.state.app_revision)}
            self.respond(200, "application/json", json.dumps(payload).encode("utf-8"))
            return
        self.respond(404, "text/plain; charset=utf-8", b"not found")


class PwaBrowserEvidenceTests(unittest.TestCase):
    def wait_for_state(self, browser: Any, expected: str, timeout: float = 5.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            value = browser.execute(
                """
                return {
                  state: document.body.dataset.state,
                  current: document.body.dataset.current,
                  activeRevision: document.body.dataset.activeRevision,
                  status: document.getElementById('status').textContent,
                  value: document.getElementById('value').textContent,
                  shellExists: Boolean(document.getElementById('shell')),
                };
                """
            )
            if isinstance(value, dict):
                last = value
                if value.get("state") == expected:
                    return value
            time.sleep(0.02)
        self.fail(f"browser did not reach state {expected!r}; last={last!r}")

    def set_offline(self, browser: Any, offline: bool) -> None:
        browser.cdp("Network.enable", {})
        browser.cdp(
            "Network.emulateNetworkConditions",
            {
                "offline": offline,
                "latency": 0,
                "downloadThroughput": 0 if offline else -1,
                "uploadThroughput": 0 if offline else -1,
            },
        )

    def test_mutable_origin_proves_pwa_browser_evidence_families(self) -> None:
        state = OriginState()
        server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        server.fixture_state = state  # type: ignore[attr-defined]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_port}"
        try:
            with _open_webdriver_session() as browser:
                browser.navigate(origin + "/app")
                initial = self.wait_for_state(browser, "current")
                self.assertEqual(initial["value"], "revision-1")
                self.assertEqual(initial["current"], "true")

                structure = browser.execute(
                    """
                    const manifestLink = document.querySelector('link[rel="manifest"]');
                    const favicon = document.querySelector('link[rel="icon"]');
                    const apple = document.querySelector('link[rel="apple-touch-icon"]');
                    const xhr = new XMLHttpRequest();
                    xhr.open('GET', manifestLink.href, false);
                    xhr.send();
                    const manifest = JSON.parse(xhr.responseText);
                    const statuses = {};
                    for (const icon of manifest.icons) {
                      const request = new XMLHttpRequest();
                      request.open('GET', new URL(icon.src, location.href).href, false);
                      request.send();
                      statuses[icon.src] = request.status;
                    }
                    const appleRequest = new XMLHttpRequest();
                    appleRequest.open('GET', apple.href, false);
                    appleRequest.send();
                    const faviconRequest = new XMLHttpRequest();
                    faviconRequest.open('GET', favicon.href, false);
                    faviconRequest.send();
                    return {
                      secureContext: window.isSecureContext,
                      manifestLinked: Boolean(manifestLink),
                      manifestStatus: xhr.status,
                      startUrl: manifest.start_url,
                      scope: manifest.scope,
                      iconStatuses: statuses,
                      hasSvg: manifest.icons.some((icon) => icon.type === 'image/svg+xml'),
                      hasMaskable: manifest.icons.some((icon) => String(icon.purpose || '').split(/\\s+/).includes('maskable')),
                      faviconHref: new URL(favicon.href).pathname,
                      faviconType: favicon.type,
                      faviconStatus: faviconRequest.status,
                      appleHref: new URL(apple.href).pathname,
                      appleStatus: appleRequest.status,
                    };
                    """
                )
                self.assertEqual(
                    structure,
                    {
                        "secureContext": True,
                        "manifestLinked": True,
                        "manifestStatus": 200,
                        "startUrl": "/app",
                        "scope": "/app/",
                        "iconStatuses": {
                            "/app-icon.svg": 200,
                            "/app-icon-192.png": 200,
                            "/app-icon-512.png": 200,
                        },
                        "hasSvg": True,
                        "hasMaskable": True,
                        "faviconHref": "/favicon.svg",
                        "faviconType": "image/svg+xml",
                        "faviconStatus": 200,
                        "appleHref": "/apple-touch-icon.png",
                        "appleStatus": 200,
                    },
                )

                self.set_offline(browser, True)
                browser.execute("window.refreshData(); return true;")
                offline_cached = self.wait_for_state(browser, "freshness-unverified")
                self.assertEqual(offline_cached["value"], "revision-1")
                self.assertEqual(offline_cached["current"], "false")
                self.assertIn("unverified", offline_cached["status"].lower())
                self.assertTrue(offline_cached["shellExists"])

                state.data_revision = 2
                state.data_delay = 0.35
                self.set_offline(browser, False)
                browser.execute("window.refreshData(); return document.body.dataset.state;")
                pending = self.wait_for_state(browser, "revalidating")
                self.assertEqual(pending["current"], "false")
                revalidated = self.wait_for_state(browser, "current")
                self.assertEqual(revalidated["value"], "revision-2")
                self.assertEqual(revalidated["current"], "true")
                self.assertNotEqual(revalidated["value"], offline_cached["value"])
                state.data_delay = 0.0

                browser.execute("localStorage.removeItem('cached-data'); return true;")
                self.set_offline(browser, True)
                browser.execute("window.refreshData(); return true;")
                unavailable = self.wait_for_state(browser, "offline-unavailable")
                self.assertEqual(unavailable["value"], "")
                self.assertEqual(unavailable["current"], "false")
                self.assertTrue(unavailable["shellExists"])
                self.assertIn("offline", unavailable["status"].lower())

                self.set_offline(browser, False)
                browser.execute("window.refreshData(); return true;")
                recovered = self.wait_for_state(browser, "current")
                self.assertEqual(recovered["value"], "revision-2")

                state.app_revision = 2
                browser.execute("window.checkUpdate(); return true;")
                available = self.wait_for_state(browser, "update-available")
                self.assertEqual(available["activeRevision"], "1")
                self.assertEqual(available["current"], "false")
                browser.execute("window.applyUpdate(); return true;")
                applying = self.wait_for_state(browser, "update-applying")
                self.assertEqual(applying["current"], "false")
                applied = self.wait_for_state(browser, "update-applied")
                self.assertEqual(applied["activeRevision"], "2")
                self.assertEqual(applied["current"], "true")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
