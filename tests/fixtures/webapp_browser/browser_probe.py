from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf"


class BrowserProbeError(RuntimeError):
    pass


def _chromedriver_path() -> str | None:
    executable = "chromedriver.exe" if os.name == "nt" else "chromedriver"
    configured = os.environ.get("CHROMEWEBDRIVER")
    if configured:
        candidate = Path(configured)
        if candidate.is_dir():
            candidate = candidate / executable
        if candidate.is_file():
            return str(candidate)
    return shutil.which("chromedriver")


def browser_runtime_available() -> bool:
    return _chromedriver_path() is not None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


class _WebDriverSession:
    def __init__(self) -> None:
        driver = _chromedriver_path()
        if driver is None:
            raise BrowserProbeError(
                "ChromeDriver is required for browser-sensitive Webapp evidence"
            )
        self._port = _free_port()
        self._service = subprocess.Popen(
            [driver, f"--port={self._port}", "--allowed-ips="],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._session_id: str | None = None
        self._wait_until_ready()
        value = self._request(
            "POST",
            "/session",
            {
                "capabilities": {
                    "alwaysMatch": {
                        "browserName": "chrome",
                        "goog:chromeOptions": {
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
                        },
                    }
                }
            },
        )
        if not isinstance(value, dict) or not isinstance(value.get("sessionId"), str):
            self.close()
            raise BrowserProbeError(
                f"ChromeDriver returned an invalid session response: {value!r}"
            )
        self._session_id = value["sessionId"]

    def _service_output(self) -> str:
        if self._service.poll() is None:
            return ""
        stdout = self._service.stdout.read() if self._service.stdout is not None else ""
        stderr = self._service.stderr.read() if self._service.stderr is not None else ""
        return (stdout + stderr).strip()

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + 10.0
        last_error = ""
        while time.monotonic() < deadline:
            if self._service.poll() is not None:
                output = self._service_output()
                raise BrowserProbeError(
                    "ChromeDriver exited before becoming ready"
                    + (f": {output}" if output else "")
                )
            try:
                request = Request(
                    f"http://127.0.0.1:{self._port}/status",
                    method="GET",
                )
                with urlopen(request, timeout=1) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if isinstance(payload, dict) and isinstance(payload.get("value"), dict):
                    if payload["value"].get("ready") is True:
                        return
            except (OSError, URLError, json.JSONDecodeError) as exc:
                last_error = str(exc)
            time.sleep(0.05)
        raise BrowserProbeError(
            "ChromeDriver did not become ready within 10 seconds"
            + (f": {last_error}" if last_error else "")
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        data = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = Request(
            f"http://127.0.0.1:{self._port}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=15) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise BrowserProbeError(
                f"WebDriver {method} {path} failed with HTTP {exc.code}: {raw}"
            ) from exc
        except URLError as exc:
            raise BrowserProbeError(
                f"WebDriver {method} {path} failed: {exc}"
            ) from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BrowserProbeError(
                f"WebDriver {method} {path} returned invalid JSON: {raw}"
            ) from exc
        if not isinstance(decoded, dict) or "value" not in decoded:
            raise BrowserProbeError(
                f"WebDriver {method} {path} returned an invalid payload: {decoded!r}"
            )
        value = decoded["value"]
        if isinstance(value, dict) and isinstance(value.get("error"), str):
            raise BrowserProbeError(
                f"WebDriver {method} {path} failed: "
                f"{value.get('error')}: {value.get('message', '')}"
            )
        return value

    @property
    def _prefix(self) -> str:
        if self._session_id is None:
            raise BrowserProbeError("WebDriver session is not initialized")
        return f"/session/{self._session_id}"

    def navigate(self, url: str) -> None:
        self._request("POST", f"{self._prefix}/url", {"url": url})

    def set_window(self, width: int, height: int) -> None:
        self._request(
            "POST",
            f"{self._prefix}/window/rect",
            {"width": width, "height": height, "x": 0, "y": 0},
        )

    def execute(self, script: str, *arguments: Any) -> Any:
        return self._request(
            "POST",
            f"{self._prefix}/execute/sync",
            {"script": script, "args": list(arguments)},
        )

    def _element(self, selector: str) -> dict[str, str]:
        value = self._request(
            "POST",
            f"{self._prefix}/element",
            {"using": "css selector", "value": selector},
        )
        if not isinstance(value, dict) or not isinstance(value.get(ELEMENT_KEY), str):
            raise BrowserProbeError(f"WebDriver could not resolve element {selector!r}")
        return {ELEMENT_KEY: value[ELEMENT_KEY]}

    def send_keys(self, selector: str, text: str) -> None:
        element = self._element(selector)
        self._request(
            "POST",
            f"{self._prefix}/element/{element[ELEMENT_KEY]}/value",
            {"text": text},
        )

    def pointer_activate(self, selector: str, pointer_type: str) -> None:
        element = self._element(selector)
        self._request(
            "POST",
            f"{self._prefix}/actions",
            {
                "actions": [
                    {
                        "type": "pointer",
                        "id": f"{pointer_type}-pointer",
                        "parameters": {"pointerType": pointer_type},
                        "actions": [
                            {
                                "type": "pointerMove",
                                "duration": 0,
                                "origin": element,
                                "x": 0,
                                "y": 0,
                            },
                            {"type": "pointerDown", "button": 0},
                            {"type": "pause", "duration": 50},
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ]
            },
        )
        self._request("DELETE", f"{self._prefix}/actions")

    def cdp(self, command: str, parameters: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            f"{self._prefix}/goog/cdp/execute",
            {"cmd": command, "params": parameters},
        )

    def close(self) -> None:
        if self._session_id is not None:
            try:
                self._request("DELETE", f"/session/{self._session_id}")
            except BrowserProbeError:
                pass
            self._session_id = None
        if self._service.poll() is None:
            self._service.terminate()
            try:
                self._service.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._service.kill()
                self._service.wait(timeout=5)

    def __enter__(self) -> "_WebDriverSession":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise BrowserProbeError(message)


def _layout_snapshot(session: _WebDriverSession) -> dict[str, Any]:
    value = session.execute(
        """
        const layout = document.querySelector(".layout");
        const context = document.querySelector(".context");
        const scrollRegion = document.querySelector(".scroll-region");
        const action = document.querySelector("#primary-action");
        if (!layout || !scrollRegion || !action) {
          return {missing: true};
        }
        const layoutStyle = getComputedStyle(layout);
        const columns = layoutStyle.gridTemplateColumns.trim();
        const contextRect = context ? context.getBoundingClientRect() : null;
        const horizontalScrollers = Array.from(document.querySelectorAll("*"))
          .filter((element) => {
            const style = getComputedStyle(element);
            if (style.display === "none" || style.visibility === "hidden") {
              return false;
            }
            if (style.overflowX !== "auto" && style.overflowX !== "scroll") {
              return false;
            }
            return element.scrollWidth > element.clientWidth + 1;
          })
          .map((element) => element.id || element.className || element.tagName);
        return {
          missing: false,
          innerWidth: window.innerWidth,
          columnCount: columns ? columns.split(/\\s+/).length : 0,
          contextVisible: Boolean(
            context &&
            getComputedStyle(context).display !== "none" &&
            contextRect &&
            contextRect.width > 0 &&
            contextRect.height > 0
          ),
          layoutMaxWidth: layoutStyle.maxWidth,
          pageOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
          scrollOverflowX: getComputedStyle(scrollRegion).overflowX,
          scrollRegionScrollable: scrollRegion.scrollWidth > scrollRegion.clientWidth + 1,
          horizontalScrollers,
          actionVisible: action.getBoundingClientRect().width > 0 &&
                         action.getBoundingClientRect().height > 0,
        };
        """
    )
    if not isinstance(value, dict):
        raise BrowserProbeError(f"browser layout probe returned invalid data: {value!r}")
    return value


def _zoom_snapshot(session: _WebDriverSession) -> dict[str, Any]:
    value = session.execute(
        """
        const action = document.querySelector("#primary-action");
        const viewport = window.visualViewport;
        if (!action || !viewport) {
          return {missing: true};
        }
        action.scrollIntoView({block: "center", inline: "center"});
        const rect = action.getBoundingClientRect();
        const left = viewport.offsetLeft;
        const top = viewport.offsetTop;
        const right = left + viewport.width;
        const bottom = top + viewport.height;
        const centerX = Math.min(Math.max(rect.left + rect.width / 2, left + 1), right - 1);
        const centerY = Math.min(Math.max(rect.top + rect.height / 2, top + 1), bottom - 1);
        const topElement = document.elementFromPoint(centerX, centerY);
        return {
          missing: false,
          scale: viewport.scale,
          actionVisible: rect.width > 0 && rect.height > 0,
          actionInVisualViewport:
            rect.right > left && rect.left < right && rect.bottom > top && rect.top < bottom,
          actionUnobscured:
            topElement === action || (topElement !== null && action.contains(topElement)),
          pageOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
        };
        """
    )
    if not isinstance(value, dict):
        raise BrowserProbeError(f"browser zoom probe returned invalid data: {value!r}")
    return value


def run_browser_contract_probe(url: str, viewports_contract: dict[str, Any]) -> None:
    viewports = viewports_contract.get("viewports")
    capabilities = viewports_contract.get("inputCapabilities")
    constraints = viewports_contract.get("constraints")
    if not isinstance(viewports, list) or not viewports:
        raise BrowserProbeError("viewports contract must contain at least one viewport")
    if not isinstance(capabilities, list) or not all(
        isinstance(item, str) for item in capabilities
    ):
        raise BrowserProbeError("viewports contract inputCapabilities must be strings")
    if not isinstance(constraints, dict):
        raise BrowserProbeError("viewports contract constraints must be an object")
    horizontal_scrolling = constraints.get("horizontalScrolling")
    if horizontal_scrolling not in {"never", "content-specific"}:
        raise BrowserProbeError(
            "viewports contract horizontalScrolling must be never or content-specific"
        )
    if constraints.get("zoomSupported") is not True:
        raise BrowserProbeError("browser probe requires zoomSupported=true")
    if constraints.get("orientationIndependent") is not True:
        raise BrowserProbeError("browser probe requires orientationIndependent=true")

    sample_widths: list[int] = []
    for item in viewports:
        if not isinstance(item, dict) or not isinstance(item.get("minWidthPx"), int):
            raise BrowserProbeError("viewports contract contains an invalid minWidthPx")
        minimum = item["minWidthPx"]
        sample_widths.append(max(390, minimum + 64))
    sample_widths = sorted(set(sample_widths))

    with _WebDriverSession() as session:
        session.navigate(url)

        snapshots: list[dict[str, Any]] = []
        for width in sample_widths:
            session.set_window(width, 800)
            snapshot = _layout_snapshot(session)
            _assert(snapshot.get("missing") is False, "browser fixture UI is incomplete")
            _assert(
                snapshot.get("pageOverflow") is False,
                f"page-wide horizontal overflow at viewport width {width}",
            )
            _assert(
                snapshot.get("actionVisible") is True,
                f"primary action is not visible at viewport width {width}",
            )
            if horizontal_scrolling == "never":
                _assert(
                    snapshot.get("scrollRegionScrollable") is False,
                    f"horizontalScrolling=never but the declared scroll region requires horizontal scrolling at viewport width {width}",
                )
                _assert(
                    snapshot.get("horizontalScrollers") == [],
                    f"horizontalScrolling=never but a visible horizontal scroller exists at viewport width {width}: {snapshot.get('horizontalScrollers')}",
                )
            else:
                _assert(
                    snapshot.get("scrollOverflowX") in {"auto", "scroll"},
                    "content-specific scroll region is not browser-computed as horizontally scrollable",
                )
            snapshots.append(snapshot)

        if len(snapshots) >= 2:
            structural_signatures = {
                (
                    int(item.get("columnCount", 0)),
                    bool(item.get("contextVisible")),
                    str(item.get("layoutMaxWidth")),
                )
                for item in snapshots
            }
            _assert(
                len(structural_signatures) == len(snapshots),
                "declared viewport breakpoints do not produce distinct browser layout structures",
            )

        session.set_window(390, 800)
        if horizontal_scrolling == "content-specific":
            scroll_result = session.execute(
                """
                const region = document.querySelector(".scroll-region");
                const probe = document.createElement("span");
                probe.id = "browser-wide-content-probe";
                probe.style.display = "inline-block";
                probe.style.width = "2000px";
                probe.textContent = "wide content";
                region.appendChild(probe);
                const result = {
                  regionScrollable: region.scrollWidth > region.clientWidth + 1,
                  pageOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
                };
                probe.remove();
                return result;
                """
            )
            _assert(
                isinstance(scroll_result, dict)
                and scroll_result.get("regionScrollable") is True,
                "content-specific scroll region does not contain wide content",
            )
            _assert(
                scroll_result.get("pageOverflow") is False,
                "content-specific scrolling leaks into page-wide horizontal overflow",
            )

        viewport_meta = session.execute(
            """
            const meta = document.querySelector('meta[name="viewport"]');
            return meta ? meta.content.toLowerCase() : null;
            """
        )
        _assert(isinstance(viewport_meta, str), "viewport meta is missing in browser")
        _assert(
            "user-scalable=no" not in viewport_meta
            and "maximum-scale=1" not in viewport_meta,
            "viewport metadata disables user zoom",
        )

        session.set_window(800, 800)
        session.cdp("Emulation.setPageScaleFactor", {"pageScaleFactor": 2.0})
        try:
            time.sleep(0.05)
            zoom_result = _zoom_snapshot(session)
            _assert(zoom_result.get("missing") is False, "browser zoom fixture UI is incomplete")
            _assert(
                isinstance(zoom_result.get("scale"), (int, float))
                and float(zoom_result["scale"]) >= 1.9,
                f"Chrome page scale did not reach 200%: {zoom_result.get('scale')!r}",
            )
            _assert(
                zoom_result.get("actionVisible") is True
                and zoom_result.get("actionInVisualViewport") is True,
                "primary action is not visible in the 200% visual viewport",
            )
            _assert(
                zoom_result.get("actionUnobscured") is True,
                "primary action is obscured at 200% browser page scale",
            )
            _assert(
                zoom_result.get("pageOverflow") is False,
                "layout introduces page-wide horizontal overflow at 200% browser page scale",
            )
            session.execute(
                'document.querySelector("#main-content").dataset.action = "";'
            )
            session.pointer_activate("#primary-action", "mouse")
            _assert(
                session.execute(
                    'return document.querySelector("#main-content").dataset.action;'
                )
                == "activated",
                "primary action is not operable at 200% browser page scale",
            )
        finally:
            session.cdp("Emulation.setPageScaleFactor", {"pageScaleFactor": 1.0})

        session.set_window(844, 390)
        landscape = _layout_snapshot(session)
        _assert(
            landscape.get("missing") is False
            and landscape.get("pageOverflow") is False
            and landscape.get("actionVisible") is True,
            "landscape browser layout is not independently usable",
        )

        if "keyboard" in capabilities:
            session.execute(
                'document.querySelector("#main-content").dataset.action = "";'
            )
            session.send_keys("#primary-action", "\ue007")
            _assert(
                session.execute(
                    'return document.querySelector("#main-content").dataset.action;'
                )
                == "activated",
                "keyboard Enter does not activate the primary browser action",
            )

        if "pointer" in capabilities:
            session.execute(
                'document.querySelector("#main-content").dataset.action = "";'
            )
            session.pointer_activate("#primary-action", "mouse")
            _assert(
                session.execute(
                    'return document.querySelector("#main-content").dataset.action;'
                )
                == "activated",
                "pointer activation does not activate the primary browser action",
            )

        if "touch" in capabilities:
            session.cdp(
                "Emulation.setTouchEmulationEnabled",
                {"enabled": True, "maxTouchPoints": 5},
            )
            _assert(
                session.execute("return navigator.maxTouchPoints;") >= 1,
                "touch emulation is not active in the browser runtime",
            )
            session.execute(
                'document.querySelector("#main-content").dataset.action = "";'
            )
            session.pointer_activate("#primary-action", "touch")
            _assert(
                session.execute(
                    'return document.querySelector("#main-content").dataset.action;'
                )
                == "activated",
                "touch activation does not activate the primary browser action",
            )

    print(
        "Browser Webapp proof: responsive structure, declared scrolling policy, "
        "browser page scale, orientation, and declared input capabilities passed"
    )