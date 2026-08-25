from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT_ROOT))

from task_ledger.cli import make_server


ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf"
TAB = "\ue004"
ENTER = "\ue007"
END = "\ue010"


class BrowserProofError(RuntimeError):
    pass


def driver_path() -> str:
    configured = os.environ.get("CHROMEWEBDRIVER")
    if configured:
        candidate = Path(configured)
        if candidate.is_dir():
            candidate /= "chromedriver.exe" if os.name == "nt" else "chromedriver"
        if candidate.is_file():
            return str(candidate)
    discovered = shutil.which("chromedriver")
    if discovered:
        return discovered
    raise BrowserProofError(
        "ChromeDriver is required; put chromedriver on PATH or set CHROMEWEBDRIVER"
    )


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


class BrowserSession:
    def __init__(self) -> None:
        self.port = free_port()
        self.service = subprocess.Popen(
            [driver_path(), f"--port={self.port}", "--allowed-ips="],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.session_id: str | None = None
        try:
            self.wait_ready()
            self.start_session()
        except BaseException:
            self.close()
            raise

    def start_session(self) -> None:
        chrome_options: dict[str, Any] = {
            "args": [
                "--headless=new",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-sync",
                "--metrics-recording-only",
                "--no-first-run",
                "--window-size=1024,768",
            ]
        }
        binary = os.environ.get("CHROME_BINARY")
        if binary:
            chrome_options["binary"] = binary
        value = self.request(
            "POST",
            "/session",
            {
                "capabilities": {
                    "alwaysMatch": {
                        "browserName": "chrome",
                        "goog:chromeOptions": chrome_options,
                    }
                }
            },
        )
        if not isinstance(value, dict) or not isinstance(value.get("sessionId"), str):
            self.close()
            raise BrowserProofError(f"invalid ChromeDriver session response: {value!r}")
        self.session_id = value["sessionId"]

    def wait_ready(self) -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.service.poll() is not None:
                raise BrowserProofError("ChromeDriver exited before becoming ready")
            try:
                with urlopen(f"http://127.0.0.1:{self.port}/status", timeout=1) as response:
                    value = json.load(response).get("value", {})
                if value.get("ready") is True:
                    return
            except (OSError, URLError, json.JSONDecodeError):
                pass
            time.sleep(0.05)
        raise BrowserProofError("ChromeDriver did not become ready within 10 seconds")

    def request(self, method: str, path: str, payload: object | None = None) -> Any:
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        request = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=15) as response:
                decoded = json.load(response)
        except HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise BrowserProofError(f"WebDriver {method} {path}: HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise BrowserProofError(f"WebDriver {method} {path}: {exc}") from exc
        if not isinstance(decoded, dict) or "value" not in decoded:
            raise BrowserProofError(f"invalid WebDriver response: {decoded!r}")
        value = decoded["value"]
        if isinstance(value, dict) and value.get("error"):
            raise BrowserProofError(f"WebDriver error: {value.get('message', value['error'])}")
        return value

    @property
    def prefix(self) -> str:
        if self.session_id is None:
            raise BrowserProofError("browser session is not initialized")
        return f"/session/{self.session_id}"

    def navigate(self, url: str) -> None:
        self.request("POST", f"{self.prefix}/url", {"url": url})

    def execute(self, script: str) -> Any:
        return self.request(
            "POST", f"{self.prefix}/execute/sync", {"script": script, "args": []}
        )

    def element(self, selector: str) -> dict[str, str]:
        value = self.request(
            "POST",
            f"{self.prefix}/element",
            {"using": "css selector", "value": selector},
        )
        if not isinstance(value, dict) or not isinstance(value.get(ELEMENT_KEY), str):
            raise BrowserProofError(f"element not found: {selector}")
        return {ELEMENT_KEY: value[ELEMENT_KEY]}

    def send_keys(self, selector: str, text: str) -> None:
        element = self.element(selector)[ELEMENT_KEY]
        self.send_keys_to_element(element, text)

    def send_keys_to_element(self, element: str, text: str) -> None:
        self.request(
            "POST",
            f"{self.prefix}/element/{element}/value",
            {"text": text},
        )

    def send_keys_to_active(self, text: str) -> None:
        value = self.request("GET", f"{self.prefix}/element/active")
        if not isinstance(value, dict) or not isinstance(value.get(ELEMENT_KEY), str):
            raise BrowserProofError("active browser element is unavailable")
        self.send_keys_to_element(value[ELEMENT_KEY], text)

    def tab_to(self, selector: str, count: int) -> None:
        self.send_keys_to_active(TAB * count)
        require(
            self.execute(
                f"return document.activeElement.matches({json.dumps(selector)})"
            ),
            f"keyboard traversal did not reach {selector}",
        )

    def set_viewport(self, width: int, height: int) -> None:
        self.request(
            "POST",
            f"{self.prefix}/goog/cdp/execute",
            {
                "cmd": "Emulation.setDeviceMetricsOverride",
                "params": {
                    "width": width,
                    "height": height,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            },
        )

    def set_scale(self, scale: float) -> None:
        self.request(
            "POST",
            f"{self.prefix}/goog/cdp/execute",
            {"cmd": "Emulation.setPageScaleFactor", "params": {"pageScaleFactor": scale}},
        )

    def close(self) -> None:
        try:
            if self.session_id is not None:
                try:
                    self.request("DELETE", f"/session/{self.session_id}")
                except Exception:
                    pass
                self.session_id = None
        finally:
            if self.service.poll() is None:
                self.service.terminate()
                try:
                    self.service.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.service.kill()
                    self.service.wait(timeout=5)

    def __enter__(self) -> "BrowserSession":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BrowserProofError(message)


def wait_for(session: BrowserSession, script: str, message: str) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if session.execute(script):
            return
        time.sleep(0.05)
    raise BrowserProofError(message)


def run_browser_proof(base_url: str) -> None:
    with BrowserSession() as browser:
        browser.set_viewport(320, 800)
        browser.navigate(base_url)
        layout = browser.execute(
            """
            const meta = document.querySelector('meta[name="viewport"]');
            const viewport = meta?.content.toLowerCase() || '';
            const directives = Object.fromEntries(
              viewport.split(',').map((part) => {
                const [name, ...value] = part.split('=');
                return [name.trim(), value.join('=').trim()];
              })
            );
            const userScalable = directives['user-scalable'];
            const maximumScale = Number.parseFloat(directives['maximum-scale']);
            const controls = ['#main-heading', '#title', '#new-task button', '#status'];
            const effectivelyVisible = (element) => {
              for (let current = element; current; current = current.parentElement) {
                const style = getComputedStyle(current);
                if (style.display === 'none' || style.visibility === 'hidden'
                    || Number.parseFloat(style.opacity || '1') <= 0) return false;
              }
              return true;
            };
            return {
              title: document.title,
              heading: document.querySelector('#main-heading')?.textContent,
              controlsVisible: controls.every((selector) => {
                const element = document.querySelector(selector);
                if (!element || !effectivelyVisible(element)) return false;
                const rect = element.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0
                    || rect.left < 0 || rect.top < 0
                    || rect.right > window.innerWidth
                    || rect.bottom > window.innerHeight) return false;
                const hit = document.elementFromPoint(
                  rect.left + rect.width / 2,
                  rect.top + rect.height / 2,
                );
                return hit === element || element.contains(hit);
              }),
              headingFocused: document.activeElement?.id === 'main-heading',
              overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
              nestedOverflow: [...document.querySelectorAll('body *')].some((element) => {
                const effectivelyVisible = (candidate) => {
                  for (let current = candidate; current; current = current.parentElement) {
                    const currentStyle = getComputedStyle(current);
                    if (currentStyle.display === 'none'
                        || currentStyle.visibility === 'hidden'
                        || Number.parseFloat(currentStyle.opacity || '1') <= 0) return false;
                  }
                  return true;
                };
                const style = getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return ['auto', 'scroll'].includes(style.overflowX)
                  && effectivelyVisible(element)
                  && rect.width > 0 && rect.height > 0
                  && rect.right > 0 && rect.bottom > 0
                  && rect.left < window.innerWidth && rect.top < window.innerHeight
                  && element.scrollWidth > element.clientWidth + 1;
              }),
              zoomAllowed: !['no', '0', 'false'].includes(userScalable)
                && !(Number.isFinite(maximumScale) && maximumScale <= 1),
            };
            """
        )
        require(layout["title"] == "Task Ledger", "document title is not Task Ledger")
        require(layout["heading"] == "Task Ledger", "main heading/focus target is missing")
        require(layout["headingFocused"], "route entry did not focus the declared heading")
        require(layout["controlsVisible"], "primary controls are not visible")
        require(not layout["overflow"], "page has horizontal overflow at 320px")
        require(not layout["nestedOverflow"], "nested content scrolls horizontally at 320px")
        require(layout["zoomAllowed"], "viewport directives disable or cap user zoom")

        browser.tab_to("#title", 1)
        browser.send_keys_to_active(ENTER)
        require(
            browser.execute("return document.querySelectorAll('#tasks li').length") == 0,
            "empty keyboard submission created a task",
        )
        require(
            browser.execute("return !document.querySelector('#title').checkValidity()"),
            "required-title negative path did not remain invalid",
        )

        browser.send_keys_to_active(("Keyboard" + "x" * 120) + ENTER)
        wait_for(
            browser,
            "return document.querySelectorAll('#tasks li').length === 1",
            "keyboard submission did not create a task",
        )
        populated_narrow = browser.execute(
            """
            const actions = [...document.querySelectorAll('#tasks li button')];
            const nestedOverflow = [...document.querySelectorAll('body *')].some((element) => {
              const style = getComputedStyle(element);
              const rect = element.getBoundingClientRect();
              const visible = (() => {
                for (let current = element; current; current = current.parentElement) {
                  const currentStyle = getComputedStyle(current);
                  if (currentStyle.display === 'none'
                      || currentStyle.visibility === 'hidden'
                      || Number.parseFloat(currentStyle.opacity || '1') <= 0) return false;
                }
                return true;
              })();
              return ['auto', 'scroll'].includes(style.overflowX) && visible
                && rect.width > 0 && rect.height > 0
                && rect.right > 0 && rect.bottom > 0
                && rect.left < window.innerWidth && rect.top < window.innerHeight
                && element.scrollWidth > element.clientWidth + 1;
            });
            return {
              actionsFit: actions.length === 2 && actions.every((element) => {
                for (let current = element; current; current = current.parentElement) {
                  const style = getComputedStyle(current);
                  if (style.display === 'none' || style.visibility === 'hidden'
                      || Number.parseFloat(style.opacity || '1') <= 0) return false;
                }
                const rect = element.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0
                    || rect.left < 0 || rect.top < 0
                    || rect.right > window.innerWidth
                    || rect.bottom > window.innerHeight) return false;
                const hit = document.elementFromPoint(
                  rect.left + rect.width / 2,
                  rect.top + rect.height / 2,
                );
                return hit === element || element.contains(hit);
              }),
              overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
              nestedOverflow,
            };
            """
        )
        require(populated_narrow["actionsFit"], "task actions are outside the narrow viewport")
        require(not populated_narrow["overflow"], "populated narrow state has page overflow")
        require(
            not populated_narrow["nestedOverflow"],
            "populated narrow state has nested horizontal scrolling",
        )
        browser.navigate(base_url)
        wait_for(
            browser,
            "return document.querySelectorAll('#tasks li button').length === 2",
            "task actions did not hydrate after navigation",
        )
        browser.tab_to("#title", 1)
        browser.tab_to("#tasks li:first-child button:first-of-type", 3)
        browser.send_keys_to_active(ENTER)
        wait_for(
            browser,
            "return document.querySelector('#tasks li span')?.textContent.includes('(completed)')",
            "keyboard activation did not complete the task",
        )
        browser.navigate(base_url)
        wait_for(
            browser,
            """return document.querySelectorAll('#tasks li').length === 1
                && document.querySelector('#tasks li span').textContent.includes('(completed)')""",
            "completed task did not hydrate before the next submission",
        )
        browser.tab_to("#title", 1)
        browser.send_keys_to_active("Open task" + ENTER)
        wait_for(
            browser,
            "return document.querySelectorAll('#tasks li').length === 2",
            "second keyboard submission did not create an open task",
        )
        browser.navigate(base_url)
        wait_for(
            browser,
            "return document.querySelectorAll('#tasks li').length === 2",
            "tasks did not hydrate before keyboard filtering",
        )
        browser.tab_to("#title", 1)
        browser.tab_to("#status", 2)
        browser.send_keys_to_active(END)
        wait_for(
            browser,
            """return document.querySelector('#status').value === 'completed'
                && document.querySelectorAll('#tasks li').length === 1
                && document.querySelector('#tasks li span').textContent.includes('(completed)')""",
            "keyboard filter did not select and isolate the completed task",
        )
        require(
            browser.execute("return document.activeElement.matches('#status')"),
            "status filter lost keyboard focus after selection",
        )
        browser.tab_to("#tasks li button:first-of-type", 1)
        browser.tab_to("#tasks li button:last-of-type", 1)
        browser.send_keys_to_active(ENTER)
        wait_for(
            browser,
            "return document.querySelectorAll('#tasks li').length === 0",
            "keyboard activation did not remove the task from the completed filter",
        )
        browser.navigate(base_url)
        wait_for(
            browser,
            """return document.querySelector('#status').value === 'all'
                && document.querySelectorAll('#tasks li').length === 1
                && document.querySelector('#tasks li span').textContent === 'Open task'""",
            "deleted task remained present in the unfiltered browser state",
        )

        browser.set_viewport(800, 390)
        landscape = browser.execute(
            """
            const controls = [
              ...['#title', '#new-task button', '#status'].map(
                (selector) => document.querySelector(selector)
              ),
              ...document.querySelectorAll('#tasks li button'),
            ];
            const effectivelyVisible = (element) => {
              for (let current = element; current; current = current.parentElement) {
                const style = getComputedStyle(current);
                if (style.display === 'none' || style.visibility === 'hidden'
                    || Number.parseFloat(style.opacity || '1') <= 0) return false;
              }
              return true;
            };
            return {
              controlsVisible: controls.length >= 5 && controls.every((element) => {
                const rect = element?.getBoundingClientRect();
                if (!element || !effectivelyVisible(element)
                    || !rect || rect.width <= 0 || rect.height <= 0
                    || rect.left < 0 || rect.top < 0
                    || rect.right > window.innerWidth
                    || rect.bottom > window.innerHeight) return false;
                const hit = document.elementFromPoint(
                  rect.left + rect.width / 2,
                  rect.top + rect.height / 2,
                );
                return hit === element || element.contains(hit);
              }),
              overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
              nestedOverflow: [...document.querySelectorAll('body *')].some((element) => {
                const effectivelyVisible = (candidate) => {
                  for (let current = candidate; current; current = current.parentElement) {
                    const currentStyle = getComputedStyle(current);
                    if (currentStyle.display === 'none'
                        || currentStyle.visibility === 'hidden'
                        || Number.parseFloat(currentStyle.opacity || '1') <= 0) return false;
                  }
                  return true;
                };
                const style = getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return ['auto', 'scroll'].includes(style.overflowX)
                  && effectivelyVisible(element)
                  && rect.width > 0 && rect.height > 0
                  && rect.right > 0 && rect.bottom > 0
                  && rect.left < window.innerWidth && rect.top < window.innerHeight
                  && element.scrollWidth > element.clientWidth + 1;
              }),
            };
            """
        )
        require(landscape["controlsVisible"], "primary controls are not usable in landscape")
        require(not landscape["overflow"], "page has horizontal overflow in landscape viewport")
        require(
            not landscape["nestedOverflow"],
            "nested content scrolls horizontally in landscape viewport",
        )
        browser.set_viewport(800, 800)
        browser.set_scale(2.0)
        time.sleep(0.1)
        zoom = browser.execute(
            """
            const viewport = window.visualViewport;
            const controls = [
              ...['#title', '#new-task button', '#status'].map(
                (selector) => document.querySelector(selector)
              ),
              ...document.querySelectorAll('#tasks li button'),
            ];
            const effectivelyVisible = (element) => {
              for (let current = element; current; current = current.parentElement) {
                const style = getComputedStyle(current);
                if (style.display === 'none' || style.visibility === 'hidden'
                    || Number.parseFloat(style.opacity || '1') <= 0) return false;
              }
              return true;
            };
            const reachable = controls.length >= 5 && controls.every((element) => {
              const rect = element?.getBoundingClientRect();
              if (!element || !effectivelyVisible(element)
                  || !rect || rect.width <= 0 || rect.height <= 0
                  || rect.left < viewport.offsetLeft
                  || rect.right > viewport.offsetLeft + viewport.width
                  || rect.top < viewport.offsetTop
                  || rect.bottom > viewport.offsetTop + viewport.height) return false;
              const hit = document.elementFromPoint(
                rect.left + rect.width / 2,
                rect.top + rect.height / 2,
              );
              return hit === element || element.contains(hit);
            });
            return {
              scale: viewport?.scale || 0,
              reachable,
              layoutOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
            };
            """
        )
        require(float(zoom["scale"]) >= 1.9, "browser did not reach 200% page scale")
        require(zoom["reachable"], "primary controls are not reachable at 200% scale")
        require(
            not zoom["layoutOverflow"],
            "200% scale exposed pre-existing page-wide horizontal overflow",
        )
        browser.navigate(base_url)
        wait_for(
            browser,
            """return document.querySelectorAll('#tasks li').length === 1
                && document.querySelector('#tasks li span').textContent === 'Open task'""",
            "open task did not hydrate before the zoom submission",
        )
        browser.tab_to("#title", 1)
        browser.send_keys_to_active("Zoom task" + ENTER)
        wait_for(
            browser,
            """return document.querySelector('#title').value === ''
                && document.querySelectorAll('#tasks li').length === 2
                && [...document.querySelectorAll('#tasks li span')]
                    .some((element) => element.textContent === 'Zoom task')""",
            "zoom keyboard submission did not create and render its task",
        )

        browser.navigate(base_url + "missing")
        missing = browser.execute(
            """
            const navigation = performance.getEntriesByType('navigation')[0];
            return {
              status: navigation?.responseStatus || 0,
              body: document.body.textContent.toLowerCase(),
              hasApplicationHeading: Boolean(document.querySelector('#main-heading')),
            };
            """
        )
        require(missing["status"] == 404, "unknown route did not return HTTP 404")
        require("not found" in missing["body"], "unknown-route error body is not visible")
        require(
            not missing["hasApplicationHeading"],
            "unknown route rendered the normal application UI",
        )


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        server = make_server(str(Path(temp_dir) / "tasks.db"), "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            run_browser_proof(f"http://127.0.0.1:{server.server_port}/")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    print("Task Ledger browser proof: viewport and keyboard positive/negative paths passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
