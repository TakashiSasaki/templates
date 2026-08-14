#!/usr/bin/env python3
"""Run deterministic mobile layout checks against a built documentation site."""

from __future__ import annotations

import argparse
import html
import json
import math
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit


HARNESS_PATH = "/__mobile-layout-check__.html"
VIEWPORTS = ((360, 800), (390, 844), (412, 915))
SCREENSHOT_VIEWPORT = (390, 844)


@dataclass(frozen=True)
class CheckCase:
    name: str
    path: str
    kind: str


CASES = (
    CheckCase("landing", "/", "landing"),
    CheckCase("policy", "/policy/", "document"),
    CheckCase("repository-trees", "/repository-trees/", "repository-table"),
    CheckCase(
        "webapp-template",
        "/repository-trees/webapp/template/",
        "document",
    ),
)


class MobileLayoutError(RuntimeError):
    """Raised when the browser cannot produce trustworthy layout evidence."""


class ResultParser(HTMLParser):
    """Extract the text content of the harness result element."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture = False
        self.result: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "pre":
            return
        attributes = dict(attrs)
        if attributes.get("id") == "result":
            self._capture = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre" and self._capture:
            self._capture = False

    def handle_data(self, data: str) -> None:
        if self._capture:
            self.result.append(data)


def harness_html() -> str:
    """Return a same-origin harness that measures a target page in an iframe."""

    return """<!doctype html>
<meta charset="utf-8">
<title>Mobile layout check</title>
<style>
  html, body { margin: 0; padding: 0; }
  iframe {
    position: absolute;
    left: -10000px;
    top: 0;
    border: 0;
  }
  #result { white-space: pre-wrap; }
</style>
<iframe id="target" title="layout target"></iframe>
<pre id="result">{"ready":false}</pre>
<script>
(() => {
  const params = new URLSearchParams(location.search);
  const target = params.get("target");
  const width = Number(params.get("width"));
  const height = Number(params.get("height"));
  const result = document.getElementById("result");
  const frame = document.getElementById("target");

  if (!target || !target.startsWith("/") || target.startsWith("//")
      || target.includes("\\\\")
      || !Number.isInteger(width) || !Number.isInteger(height)
      || width < 240 || width > 800 || height < 320 || height > 1400) {
    result.textContent = JSON.stringify({ready: false, error: "invalid harness parameters"});
    return;
  }

  frame.style.width = `${width}px`;
  frame.style.height = `${height}px`;

  const number = (value) => {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const box = (element) => {
    if (!element) {
      return null;
    }
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      top: rect.top,
      left: rect.left,
      width: rect.width,
      height: rect.height,
      paddingTop: number(style.paddingTop),
      paddingRight: number(style.paddingRight),
      paddingBottom: number(style.paddingBottom),
      paddingLeft: number(style.paddingLeft),
      marginTop: number(style.marginTop),
      marginBottom: number(style.marginBottom),
      fontSize: number(style.fontSize),
      lineHeight: number(style.lineHeight),
      whiteSpace: style.whiteSpace,
      overflowWrap: style.overflowWrap,
      wordBreak: style.wordBreak,
    };
  };

  frame.addEventListener("load", () => {
    setTimeout(() => {
      try {
        const doc = frame.contentDocument;
        const win = frame.contentWindow;
        const root = doc.documentElement;
        const content = doc.querySelector(".md-content__inner");
        const breadcrumb = doc.querySelector(".md-path");
        const heading = doc.querySelector(".portal-cover h1, .md-content__inner > h1");
        const cover = doc.querySelector(".portal-cover");
        const lead = doc.querySelector(".portal-cover__lead");
        const buttons = Array.from(doc.querySelectorAll(".portal-cover__button"));
        const revision = Array.from(doc.querySelectorAll("table code")).find(
          (element) => /^[0-9a-f]{40}$/.test(element.textContent.trim())
        );
        const revisionTable = revision ? revision.closest("table") : null;
        const revisionStyle = revision ? getComputedStyle(revision) : null;
        const revisionRect = revision ? revision.getBoundingClientRect() : null;

        result.textContent = JSON.stringify({
          ready: true,
          target,
          viewport: {
            width: win.innerWidth,
            height: win.innerHeight,
          },
          page: {
            clientWidth: root.clientWidth,
            scrollWidth: root.scrollWidth,
          },
          content: box(content),
          breadcrumb: box(breadcrumb),
          heading: box(heading),
          cover: box(cover),
          lead: box(lead),
          buttons: buttons.map(box),
          revision: revision ? {
            text: revision.textContent.trim(),
            height: revisionRect.height,
            lineHeight: number(revisionStyle.lineHeight),
            whiteSpace: revisionStyle.whiteSpace,
            overflowWrap: revisionStyle.overflowWrap,
            wordBreak: revisionStyle.wordBreak,
            rectCount: revision.getClientRects().length,
          } : null,
          revisionTable: revisionTable ? {
            clientWidth: revisionTable.clientWidth,
            scrollWidth: revisionTable.scrollWidth,
          } : null,
        });
      } catch (error) {
        result.textContent = JSON.stringify({
          ready: false,
          error: String(error),
        });
      }
    }, 250);
  }, {once: true});

  frame.src = target;
})();
</script>
"""


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MobileLayoutError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise MobileLayoutError(f"{label} must be finite")
    return result


def validate_metrics(
    case: CheckCase,
    width: int,
    height: int,
    metrics: dict[str, Any],
) -> list[str]:
    """Return human-readable failures for one measured viewport."""

    failures: list[str] = []
    if metrics.get("ready") is not True:
        return [f"harness did not become ready: {metrics.get('error', 'unknown error')}"]

    viewport = metrics.get("viewport")
    page = metrics.get("page")
    if not isinstance(viewport, dict) or not isinstance(page, dict):
        return ["harness did not return viewport/page metrics"]

    try:
        measured_width = _number(viewport.get("width"), "viewport.width")
        measured_height = _number(viewport.get("height"), "viewport.height")
        client_width = _number(page.get("clientWidth"), "page.clientWidth")
        scroll_width = _number(page.get("scrollWidth"), "page.scrollWidth")
    except MobileLayoutError as exc:
        return [str(exc)]

    if abs(measured_width - width) > 1:
        failures.append(
            f"viewport width is {measured_width:g}px, expected {width}px"
        )
    if abs(measured_height - height) > 1:
        failures.append(
            f"viewport height is {measured_height:g}px, expected {height}px"
        )
    if scroll_width > client_width + 1:
        failures.append(
            f"page-wide horizontal overflow: {scroll_width:g}px > {client_width:g}px"
        )

    content = metrics.get("content")
    if not isinstance(content, dict):
        failures.append("missing .md-content__inner")
    else:
        try:
            if _number(content.get("paddingTop"), "content.paddingTop") > 8:
                failures.append("mobile content top padding exceeds 8px")
        except MobileLayoutError as exc:
            failures.append(str(exc))

    breadcrumb = metrics.get("breadcrumb")
    if isinstance(breadcrumb, dict):
        try:
            if _number(breadcrumb.get("paddingTop"), "breadcrumb.paddingTop") > 8:
                failures.append("mobile breadcrumb top padding exceeds 8px")
        except MobileLayoutError as exc:
            failures.append(str(exc))

    heading = metrics.get("heading")
    if not isinstance(heading, dict):
        failures.append("missing visible page heading")
    else:
        try:
            if _number(heading.get("marginBottom"), "heading.marginBottom") > 22:
                failures.append("mobile heading bottom margin exceeds 22px")
        except MobileLayoutError as exc:
            failures.append(str(exc))

    if case.kind == "landing":
        cover = metrics.get("cover")
        lead = metrics.get("lead")
        buttons = metrics.get("buttons")
        if not isinstance(cover, dict):
            failures.append("missing portal cover")
        else:
            try:
                if _number(cover.get("paddingTop"), "cover.paddingTop") > 20:
                    failures.append("portal cover top padding exceeds 20px")
            except MobileLayoutError as exc:
                failures.append(str(exc))
        if not isinstance(lead, dict):
            failures.append("missing portal lead")
        else:
            try:
                if _number(lead.get("lineHeight"), "lead.lineHeight") > 27:
                    failures.append("portal lead line height exceeds 27px")
            except MobileLayoutError as exc:
                failures.append(str(exc))
        if not isinstance(buttons, list) or not buttons:
            failures.append("missing portal actions")
        else:
            for index, button in enumerate(buttons):
                if not isinstance(button, dict):
                    failures.append(f"portal action {index} metrics are invalid")
                    continue
                try:
                    if _number(button.get("height"), f"buttons[{index}].height") < 48:
                        failures.append(
                            f"portal action {index} is shorter than 48px"
                        )
                except MobileLayoutError as exc:
                    failures.append(str(exc))

    if case.kind == "repository-table":
        revision = metrics.get("revision")
        table = metrics.get("revisionTable")
        if not isinstance(revision, dict):
            failures.append("missing full revision token in repository table")
        else:
            if revision.get("whiteSpace") != "nowrap":
                failures.append("repository revision is allowed to wrap")
            if revision.get("overflowWrap") != "normal":
                failures.append("repository revision overflow-wrap is not normal")
            if revision.get("wordBreak") != "normal":
                failures.append("repository revision word-break is not normal")
            if revision.get("rectCount") != 1:
                failures.append("repository revision occupies multiple line boxes")
            try:
                line_height = _number(revision.get("lineHeight"), "revision.lineHeight")
                token_height = _number(revision.get("height"), "revision.height")
                if token_height > line_height * 1.5:
                    failures.append("repository revision is taller than one text line")
            except MobileLayoutError as exc:
                failures.append(str(exc))
        if not isinstance(table, dict):
            failures.append("missing repository revision table metrics")
        else:
            try:
                table_client = _number(table.get("clientWidth"), "revisionTable.clientWidth")
                table_scroll = _number(table.get("scrollWidth"), "revisionTable.scrollWidth")
                if table_scroll < table_client:
                    failures.append("repository table scroll geometry is invalid")
            except MobileLayoutError as exc:
                failures.append(str(exc))

    return failures


def parse_harness_result(document: str) -> dict[str, Any]:
    parser = ResultParser()
    parser.feed(document)
    if not parser.result:
        raise MobileLayoutError("browser output did not contain harness result")
    raw = html.unescape("".join(parser.result)).strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MobileLayoutError(f"harness result is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise MobileLayoutError("harness result must be an object")
    return value


def _browser_runtime_arguments(profile: str, *, no_sandbox: bool) -> list[str]:
    """Return browser-wide flags, keeping sandbox disablement opt-in."""

    arguments = [
        "--headless=new",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--force-device-scale-factor=1",
        f"--user-data-dir={profile}",
    ]
    if no_sandbox:
        arguments.append("--no-sandbox")
    return arguments


def _run_browser(
    browser: Path,
    arguments: list[str],
    *,
    no_sandbox: bool = False,
    timeout: int = 45,
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="mobile-layout-chrome-") as profile:
        command = [
            str(browser),
            *_browser_runtime_arguments(profile, no_sandbox=no_sandbox),
            *arguments,
        ]
        try:
            return subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            detail = ""
            if isinstance(exc, subprocess.CalledProcessError):
                output = exc.stderr or exc.stdout or ""
                detail = output.strip()[-2000:]
            elif isinstance(exc, subprocess.TimeoutExpired):
                detail = "browser timed out"
            suffix = f": {detail}" if detail else ""
            raise MobileLayoutError(f"unable to run headless browser{suffix}") from exc


def measure(
    browser: Path,
    base_url: str,
    case: CheckCase,
    width: int,
    height: int,
    *,
    no_sandbox: bool = False,
) -> dict[str, Any]:
    query = urlencode({"target": case.path, "width": width, "height": height})
    result = _run_browser(
        browser,
        [
            "--dump-dom",
            "--virtual-time-budget=4000",
            f"--window-size={max(width, 800)},{max(height, 600)}",
            f"{base_url}{HARNESS_PATH}?{query}",
        ],
        no_sandbox=no_sandbox,
    )
    return parse_harness_result(result.stdout)


def screenshot(
    browser: Path,
    base_url: str,
    case: CheckCase,
    width: int,
    height: int,
    destination: Path,
    *,
    no_sandbox: bool = False,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run_browser(
        browser,
        [
            f"--window-size={width},{height}",
            f"--screenshot={destination.resolve()}",
            f"{base_url}{case.path}",
        ],
        no_sandbox=no_sandbox,
    )
    if not destination.is_file() or destination.stat().st_size == 0:
        raise MobileLayoutError(f"browser did not create screenshot {destination}")


def serve(site_root: Path) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    harness = harness_html().encode("utf-8")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(site_root), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            if urlsplit(self.path).path == HARNESS_PATH:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(harness)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(harness)
                return
            super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, f"http://{host}:{port}"


def run_checks(
    site_root: Path,
    browser: Path,
    output_root: Path,
    *,
    no_sandbox: bool = False,
) -> None:
    if not site_root.is_dir():
        raise MobileLayoutError(f"site root does not exist: {site_root}")
    if not (site_root / "index.html").is_file():
        raise MobileLayoutError(f"site root has no index.html: {site_root}")
    if not browser.is_file():
        raise MobileLayoutError(f"browser executable does not exist: {browser}")

    output_root.mkdir(parents=True, exist_ok=True)
    server, thread, base_url = serve(site_root)
    report: dict[str, Any] = {
        "schema_version": 1,
        "viewports": [{"width": width, "height": height} for width, height in VIEWPORTS],
        "checks": [],
        "failures": [],
    }
    failures: list[str] = []

    try:
        for case in CASES:
            for width, height in VIEWPORTS:
                try:
                    metrics = measure(
                        browser,
                        base_url,
                        case,
                        width,
                        height,
                        no_sandbox=no_sandbox,
                    )
                    case_failures = validate_metrics(case, width, height, metrics)
                except MobileLayoutError as exc:
                    metrics = {"ready": False, "error": str(exc)}
                    case_failures = [str(exc)]
                prefix = f"{case.name} {width}x{height}"
                failures.extend(f"{prefix}: {failure}" for failure in case_failures)
                report["checks"].append(
                    {
                        "case": case.name,
                        "path": case.path,
                        "width": width,
                        "height": height,
                        "metrics": metrics,
                        "failures": case_failures,
                    }
                )

        width, height = SCREENSHOT_VIEWPORT
        for case in CASES:
            destination = output_root / f"{case.name}-{width}x{height}.png"
            try:
                screenshot(
                    browser,
                    base_url,
                    case,
                    width,
                    height,
                    destination,
                    no_sandbox=no_sandbox,
                )
            except MobileLayoutError as exc:
                failures.append(f"{case.name} screenshot: {exc}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    report["failures"] = failures
    (output_root / "metrics.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if failures:
        raise MobileLayoutError(
            "mobile layout regression check failed:\n- " + "\n- ".join(failures)
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--no-sandbox",
        action="store_true",
        help="Disable the Chromium sandbox for restricted CI runners.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_checks(
            args.site_root.resolve(strict=True),
            args.browser.resolve(strict=True),
            args.output_root.resolve(),
            no_sandbox=args.no_sandbox,
        )
    except (OSError, MobileLayoutError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
