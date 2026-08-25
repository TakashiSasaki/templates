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
ENTER = "\ue007"


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
        self.wait_ready()
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
        self.request(
            "POST",
            f"{self.prefix}/element/{element}/value",
            {"text": text},
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
        if self.session_id is not None:
            try:
                self.request("DELETE", f"/session/{self.session_id}")
            except BrowserProofError:
                pass
            self.session_id = None
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
        browser.set_viewport(390, 800)
        browser.navigate(base_url)
        layout = browser.execute(
            """
            const meta = document.querySelector('meta[name="viewport"]');
            const controls = ['#title', '#new-task button', '#status', '#tasks'];
            return {
              title: document.title,
              heading: document.querySelector('#main-heading')?.textContent,
              controlsVisible: controls.every((selector) => {
                const element = document.querySelector(selector);
                if (!element) return false;
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              }),
              overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
              viewport: meta?.content.toLowerCase() || '',
            };
            """
        )
        require(layout["title"] == "Task Ledger", "document title is not Task Ledger")
        require(layout["heading"] == "Task Ledger", "main heading/focus target is missing")
        require(layout["controlsVisible"], "primary controls are not visible")
        require(not layout["overflow"], "page has horizontal overflow at 390px")
        require("user-scalable=no" not in layout["viewport"], "viewport disables zoom")
        require("maximum-scale=1" not in layout["viewport"], "viewport caps zoom")

        browser.send_keys("#title", ENTER)
        require(
            browser.execute("return document.querySelectorAll('#tasks li').length") == 0,
            "empty keyboard submission created a task",
        )
        require(
            browser.execute("return !document.querySelector('#title').checkValidity()"),
            "required-title negative path did not remain invalid",
        )

        browser.send_keys("#title", "Keyboard task" + ENTER)
        wait_for(
            browser,
            "return document.querySelectorAll('#tasks li').length === 1",
            "keyboard submission did not create a task",
        )
        browser.send_keys("#tasks li button:first-of-type", ENTER)
        wait_for(
            browser,
            "return document.querySelector('#tasks li span')?.textContent.includes('(completed)')",
            "keyboard activation did not complete the task",
        )
        browser.send_keys("#status", "completed" + ENTER)
        wait_for(
            browser,
            "return document.querySelectorAll('#tasks li').length === 1",
            "keyboard filter did not retain the completed task",
        )
        browser.send_keys("#tasks li button:last-of-type", ENTER)
        wait_for(
            browser,
            "return document.querySelectorAll('#tasks li').length === 0",
            "keyboard activation did not delete the task",
        )

        browser.set_viewport(800, 390)
        require(
            not browser.execute(
                "return document.documentElement.scrollWidth > window.innerWidth + 1"
            ),
            "page has horizontal overflow in landscape viewport",
        )
        browser.set_viewport(800, 800)
        browser.set_scale(2.0)
        time.sleep(0.1)
        zoom = browser.execute(
            """
            const input = document.querySelector('#title');
            const rect = input.getBoundingClientRect();
            return {
              scale: window.visualViewport?.scale || 0,
              visible: rect.width > 0 && rect.height > 0,
              overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
            };
            """
        )
        require(float(zoom["scale"]) >= 1.9, "browser did not reach 200% page scale")
        require(zoom["visible"], "title input is not operable at 200% scale")
        require(not zoom["overflow"], "200% scale caused page-wide horizontal overflow")

        browser.navigate(base_url + "missing")
        require(
            "not found" in str(browser.execute("return document.body.textContent")).lower(),
            "unknown-route negative path is not visible in the browser",
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
