#!/usr/bin/env python3
"""Run deterministic mobile layout checks against a built documentation site."""

from __future__ import annotations

import argparse
import json
import math
import threading
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable


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
        "/webapp/TEMPLATE/",
        "document",
    ),
)


MEASURE_SCRIPT = r"""
() => {
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

  const root = document.documentElement;
  const content = document.querySelector(".md-content__inner");
  const breadcrumb = document.querySelector(".md-path");
  const heading = document.querySelector(".portal-cover h1, .md-content__inner > h1");
  const cover = document.querySelector(".portal-cover");
  const lead = document.querySelector(".portal-cover__lead");
  const buttons = Array.from(document.querySelectorAll(".portal-cover__button"));
  const revision = Array.from(document.querySelectorAll("table code")).find(
    (element) => /^[0-9a-f]{40}$/.test(element.textContent.trim())
  );
  const revisionTable = revision ? revision.closest("table") : null;
  const revisionStyle = revision ? getComputedStyle(revision) : null;
  const revisionRect = revision ? revision.getBoundingClientRect() : null;

  return {
    ready: true,
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight,
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
  };
}
"""


class MobileLayoutError(RuntimeError):
    """Raised when the browser cannot produce trustworthy layout evidence."""


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
        return [f"browser measurement did not become ready: {metrics.get('error', 'unknown error')}"]

    viewport = metrics.get("viewport")
    page = metrics.get("page")
    if not isinstance(viewport, dict) or not isinstance(page, dict):
        return ["browser measurement did not return viewport/page metrics"]

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
                cover_height = _number(cover.get("height"), "cover.height")
                if cover_height > height * 0.9:
                    failures.append(
                        "portal cover consumes more than 90% of the mobile viewport height"
                    )
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
                if table_scroll + 1 < table_client:
                    failures.append("repository table scroll geometry is invalid")
            except MobileLayoutError as exc:
                failures.append(str(exc))

    return failures


def _load_playwright() -> tuple[Callable[[], Any], type[Exception]]:
    """Load Playwright lazily so the ordinary unit-test build needs no browser dependency."""

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise MobileLayoutError(
            "Playwright is required for browser layout checks; install requirements-visual.txt"
        ) from exc
    return sync_playwright, PlaywrightError


def _validate_cases() -> None:
    for case in CASES:
        if (
            not case.path.startswith("/")
            or case.path.startswith("//")
            or "\\" in case.path
        ):
            raise MobileLayoutError(f"unsafe layout-check path: {case.path!r}")


def serve(site_root: Path) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(site_root), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, f"http://{host}:{port}"


def _measure_case(
    browser: Any,
    base_url: str,
    case: CheckCase,
    width: int,
    height: int,
    screenshot_path: Path | None,
) -> dict[str, Any]:
    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
    )
    try:
        page = context.new_page()
        page.goto(f"{base_url}{case.path}", wait_until="load", timeout=15_000)
        page.wait_for_timeout(250)
        metrics = page.evaluate(MEASURE_SCRIPT)
        if not isinstance(metrics, dict):
            raise MobileLayoutError("browser measurement script returned a non-object")
        if screenshot_path is not None:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_path), full_page=False)
        return metrics
    finally:
        context.close()


def run_checks(site_root: Path, output_root: Path) -> None:
    if not site_root.is_dir():
        raise MobileLayoutError(f"site root does not exist: {site_root}")
    if not (site_root / "index.html").is_file():
        raise MobileLayoutError(f"site root has no index.html: {site_root}")
    _validate_cases()

    sync_playwright, PlaywrightError = _load_playwright()
    output_root.mkdir(parents=True, exist_ok=True)
    server, thread, base_url = serve(site_root)
    report: dict[str, Any] = {
        "schema_version": 1,
        "viewports": [
            {"width": width, "height": height} for width, height in VIEWPORTS
        ],
        "checks": [],
        "failures": [],
    }
    failures: list[str] = []

    try:
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    for case in CASES:
                        for width, height in VIEWPORTS:
                            screenshot_path = None
                            if (width, height) == SCREENSHOT_VIEWPORT:
                                screenshot_path = (
                                    output_root / f"{case.name}-{width}x{height}.png"
                                )
                            try:
                                metrics = _measure_case(
                                    browser,
                                    base_url,
                                    case,
                                    width,
                                    height,
                                    screenshot_path,
                                )
                                case_failures = validate_metrics(
                                    case, width, height, metrics
                                )
                            except (MobileLayoutError, PlaywrightError) as exc:
                                metrics = {"ready": False, "error": str(exc)}
                                case_failures = [str(exc)]
                            prefix = f"{case.name} {width}x{height}"
                            failures.extend(
                                f"{prefix}: {failure}"
                                for failure in case_failures
                            )
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
                finally:
                    browser.close()
        except PlaywrightError as exc:
            raise MobileLayoutError(f"unable to run Playwright Chromium: {exc}") from exc
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
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_checks(
            args.site_root.resolve(strict=True),
            args.output_root.resolve(),
        )
    except (OSError, MobileLayoutError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
