#!/usr/bin/env python3
"""Run deterministic Site layout checks, including repository-browser interaction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts import check_mobile_layout_core as core
except ModuleNotFoundError:
    import check_mobile_layout_core as core


CASES = core.CASES
CheckCase = core.CheckCase
MobileLayoutError = core.MobileLayoutError
_number = core._number
_validate_cases = core._validate_cases
validate_metrics = core.validate_metrics
validate_repository_viewer_metrics = core.validate_repository_viewer_metrics

REPOSITORY_BROWSER_FILTER_VIEWPORT = (390, 844)
REPOSITORY_BROWSER_FILTER_PATH = "/files/site/"
REPOSITORY_BROWSER_FILTER_ZERO_QUERY = "__templates_no_such_file_8675309__"


def validate_repository_browser_filter_metrics(metrics: dict[str, Any]) -> list[str]:
    """Validate repository-browser filter behavior measured in a real browser."""

    if metrics.get("ready") is not True:
        return [
            "repository browser filter measurement did not become ready: "
            f"{metrics.get('error', 'unknown error')}"
        ]

    failures: list[str] = []
    viewport = metrics.get("viewport")
    page = metrics.get("page")
    initial = metrics.get("initial")
    filtered = metrics.get("filtered")
    opened = metrics.get("opened")
    returned = metrics.get("returned")
    slash = metrics.get("slash")
    zero = metrics.get("zero")
    cleared = metrics.get("cleared")
    if not all(
        isinstance(value, dict)
        for value in (
            viewport,
            page,
            initial,
            filtered,
            opened,
            returned,
            slash,
            zero,
            cleared,
        )
    ):
        return ["repository browser filter measurement is incomplete"]

    width, height = REPOSITORY_BROWSER_FILTER_VIEWPORT
    try:
        measured_width = _number(viewport.get("width"), "filter viewport.width")
        measured_height = _number(viewport.get("height"), "filter viewport.height")
        client_width = _number(page.get("clientWidth"), "filter page.clientWidth")
        scroll_width = _number(page.get("scrollWidth"), "filter page.scrollWidth")
        total = int(_number(initial.get("total"), "filter initial.total"))
        filtered_visible = int(
            _number(filtered.get("visible"), "filter filtered.visible")
        )
        saved_scroll = _number(filtered.get("scrollTop"), "filter filtered.scrollTop")
        returned_scroll = _number(
            returned.get("scrollTop"), "filter returned.scrollTop"
        )
        zero_visible = int(_number(zero.get("visible"), "filter zero.visible"))
        cleared_visible = int(
            _number(cleared.get("visible"), "filter cleared.visible")
        )
    except MobileLayoutError as exc:
        return [str(exc)]

    if abs(measured_width - width) > 1 or abs(measured_height - height) > 1:
        failures.append(
            "repository browser filter viewport does not match the mobile acceptance size"
        )
    if scroll_width > client_width + 1:
        failures.append("repository browser filter causes page-wide horizontal overflow")
    if total < 1:
        failures.append("repository browser exposes no filterable files")
    if initial.get("status") != f"{total} files":
        failures.append("repository browser initial filter count is inconsistent")

    query = filtered.get("query")
    if not isinstance(query, str) or not query:
        failures.append("repository browser filter query is missing")
    if filtered_visible < 1 or filtered_visible > total:
        failures.append("repository browser filtered result count is invalid")
    if filtered.get("allMatch") is not True:
        failures.append("repository browser shows a file that does not match the query")
    if filtered.get("ancestorsOpen") is not True:
        failures.append("repository browser does not open matching file ancestors")

    selected_path = opened.get("selectedPath")
    if opened.get("mobileView") != "content":
        failures.append("repository browser quick-open did not enter Content mode")
    if not isinstance(selected_path, str) or not selected_path:
        failures.append("repository browser quick-open did not select a file")
    if opened.get("hashPath") != selected_path:
        failures.append("repository browser quick-open URL does not match the selection")
    if opened.get("filterValue") != filtered.get("broadQuery"):
        failures.append("repository browser quick-open lost the filter value")
    if opened.get("filesFocused") is not True:
        failures.append("repository browser quick-open did not focus the Files button")
    frame_src = opened.get("frameSrc")
    if not isinstance(frame_src, str) or "/files/site/content/" not in frame_src:
        failures.append("repository browser quick-open did not load a bounded viewer URL")

    if returned.get("mobileView") != "files":
        failures.append("repository browser Files return did not restore Files mode")
    if returned.get("filterValue") != filtered.get("broadQuery"):
        failures.append("repository browser Files return lost the filter value")
    if abs(returned_scroll - saved_scroll) > 1:
        failures.append("repository browser Files return did not restore tree scroll")
    if returned.get("filterFocused") is not True:
        failures.append("repository browser Files return did not restore filter focus")

    if slash.get("mobileView") != "files":
        failures.append("repository browser slash shortcut did not restore Files mode")
    if slash.get("filterValue") != filtered.get("broadQuery"):
        failures.append("repository browser slash shortcut lost the filter value")
    if slash.get("filterFocused") is not True:
        failures.append("repository browser slash shortcut did not focus the filter")

    if zero_visible != 0 or zero.get("status") != "No matching files":
        failures.append("repository browser zero-result state is not explicit")
    if cleared.get("inputValue") != "":
        failures.append("repository browser Escape did not clear the filter")
    if cleared_visible != total:
        failures.append("repository browser clear did not restore all files")
    if cleared.get("detailsRestored") is not True:
        failures.append("repository browser clear did not restore directory open state")
    if cleared.get("status") != f"{total} files":
        failures.append("repository browser clear did not restore the file count")

    return failures


def _ascii_swapcase(value: str) -> str:
    return "".join(
        character.swapcase()
        if character.isascii() and character.isalpha()
        else character
        for character in value
    )


def _visible_repository_paths(page: Any) -> list[str]:
    paths = page.locator("a[data-repository-file]:visible").evaluate_all(
        "elements => elements.map(element => element.dataset.filePath)"
    )
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise MobileLayoutError("repository browser returned invalid visible file paths")
    return paths


def _measure_repository_browser_filter(
    browser: Any,
    base_url: str,
    output_root: Path,
) -> dict[str, Any]:
    width, height = REPOSITORY_BROWSER_FILTER_VIEWPORT
    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
    )
    try:
        page = context.new_page()
        page.goto(
            f"{base_url}{REPOSITORY_BROWSER_FILTER_PATH}",
            wait_until="load",
            timeout=15_000,
        )
        filter_input = page.locator('input[aria-label="Filter files"]')
        filter_input.wait_for(state="visible", timeout=5_000)
        filter_status = page.locator("[data-repository-filter-status]")
        file_links = page.locator("a[data-repository-file]")
        total = file_links.count()
        if total < 1:
            raise MobileLayoutError("repository browser has no files to filter")
        paths = file_links.evaluate_all(
            "elements => elements.map(element => element.dataset.filePath)"
        )
        if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
            raise MobileLayoutError("repository browser file paths are invalid")
        target_path = next(
            (
                path
                for path in paths
                if "/" in path
                and any(character.isascii() and character.isalpha() for character in path)
            ),
            next(
                (
                    path
                    for path in paths
                    if any(
                        character.isascii() and character.isalpha()
                        for character in path
                    )
                ),
                paths[0],
            ),
        )
        query = _ascii_swapcase(target_path)
        details_before = page.locator(".tree details").evaluate_all(
            "elements => elements.map(element => element.open)"
        )
        initial = {
            "total": total,
            "status": filter_status.text_content() or "",
        }

        filter_input.fill(query)
        page.wait_for_timeout(50)
        filtered_paths = _visible_repository_paths(page)
        query_key = query.lower()
        target = page.locator(
            f'a[data-repository-file][data-file-path={json.dumps(target_path)}]'
        )
        ancestors_open = target.evaluate(
            "element => { let current = element.parentElement; "
            "while (current) { if (current.tagName === 'DETAILS' && !current.open) return false; "
            "current = current.parentElement; } return true; }"
        )

        # Use a broad path query for the mobile context round trip so the tree
        # retains realistic scrolling while Enter still has a deterministic
        # first visible file to open.
        broad_query = "."
        filter_input.fill(broad_query)
        page.wait_for_timeout(50)
        broad_paths = _visible_repository_paths(page)
        if not broad_paths:
            broad_query = target_path
            filter_input.fill(broad_query)
            page.wait_for_timeout(50)
            broad_paths = _visible_repository_paths(page)
        tree_scroller = page.locator(".tree")
        saved_scroll = tree_scroller.evaluate(
            "element => { const value = Math.min(137, Math.max(0, element.scrollHeight - element.clientHeight)); "
            "element.scrollTop = value; return element.scrollTop; }"
        )
        filtered = {
            "query": query,
            "visible": len(filtered_paths),
            "allMatch": all(query_key in path.lower() for path in filtered_paths),
            "ancestorsOpen": bool(ancestors_open),
            "status": filter_status.text_content() or "",
            "broadQuery": broad_query,
            "broadVisible": len(broad_paths),
            "scrollTop": saved_scroll,
        }

        filter_input.focus()
        filter_input.press("Enter")
        page.wait_for_function(
            "() => document.querySelector('[data-repository-browser]').dataset.mobileView === 'content'"
        )
        selected_path = page.locator("[data-selected-file]").text_content() or ""
        hash_path = page.evaluate(
            "() => new URLSearchParams(location.hash.slice(1)).get('file') || ''"
        )
        opened = {
            "mobileView": page.locator("[data-repository-browser]").get_attribute(
                "data-mobile-view"
            ),
            "selectedPath": selected_path,
            "hashPath": hash_path,
            "frameSrc": page.locator("iframe[name='repository-file-viewer']").get_attribute(
                "src"
            ),
            "filterValue": filter_input.input_value(),
            "filesFocused": page.locator("[data-show-files]").evaluate(
                "element => document.activeElement === element"
            ),
        }

        page.locator("[data-show-files]").click()
        page.wait_for_function(
            "() => document.querySelector('[data-repository-browser]').dataset.mobileView === 'files'"
        )
        returned = {
            "mobileView": page.locator("[data-repository-browser]").get_attribute(
                "data-mobile-view"
            ),
            "filterValue": filter_input.input_value(),
            "scrollTop": tree_scroller.evaluate("element => element.scrollTop"),
            "filterFocused": filter_input.evaluate(
                "element => document.activeElement === element"
            ),
        }

        filter_input.press("Enter")
        page.wait_for_function(
            "() => document.querySelector('[data-repository-browser]').dataset.mobileView === 'content'"
        )
        page.locator("[data-show-files]").focus()
        page.keyboard.press("/")
        page.wait_for_function(
            "() => document.querySelector('[data-repository-browser]').dataset.mobileView === 'files'"
        )
        slash = {
            "mobileView": page.locator("[data-repository-browser]").get_attribute(
                "data-mobile-view"
            ),
            "filterValue": filter_input.input_value(),
            "filterFocused": filter_input.evaluate(
                "element => document.activeElement === element"
            ),
        }

        filter_input.fill(REPOSITORY_BROWSER_FILTER_ZERO_QUERY)
        page.wait_for_timeout(50)
        zero = {
            "visible": len(_visible_repository_paths(page)),
            "status": filter_status.text_content() or "",
        }
        filter_input.press("Escape")
        page.wait_for_timeout(50)
        details_after = page.locator(".tree details").evaluate_all(
            "elements => elements.map(element => element.open)"
        )
        cleared = {
            "visible": len(_visible_repository_paths(page)),
            "inputValue": filter_input.input_value(),
            "detailsRestored": details_after == details_before,
            "status": filter_status.text_content() or "",
        }
        root = page.locator("html")
        page_metrics = root.evaluate(
            "element => ({clientWidth: element.clientWidth, scrollWidth: element.scrollWidth})"
        )
        screenshot_path = output_root / "repository-browser-filter-390x844.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=False)
        return {
            "ready": True,
            "viewport": {"width": page.evaluate("() => innerWidth"), "height": page.evaluate("() => innerHeight")},
            "page": page_metrics,
            "initial": initial,
            "filtered": filtered,
            "opened": opened,
            "returned": returned,
            "slash": slash,
            "zero": zero,
            "cleared": cleared,
        }
    finally:
        context.close()


def _run_repository_browser_filter_check(site_root: Path, output_root: Path) -> None:
    sync_playwright, PlaywrightError = core._load_playwright()
    server, thread, base_url = core.serve(site_root)
    try:
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    metrics = _measure_repository_browser_filter(
                        browser, base_url, output_root
                    )
                finally:
                    browser.close()
        except PlaywrightError as exc:
            raise MobileLayoutError(
                f"unable to run repository browser filter acceptance: {exc}"
            ) from exc
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    failures = validate_repository_browser_filter_metrics(metrics)
    report_path = output_root / "metrics.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MobileLayoutError(
            f"unable to extend browser metrics report: {report_path}"
        ) from exc
    if not isinstance(report, dict):
        raise MobileLayoutError("browser metrics report is not an object")
    report["repository_browser_filter_check"] = {
        "case": "repository-browser-filter",
        "path": REPOSITORY_BROWSER_FILTER_PATH,
        "width": REPOSITORY_BROWSER_FILTER_VIEWPORT[0],
        "height": REPOSITORY_BROWSER_FILTER_VIEWPORT[1],
        "metrics": metrics,
        "failures": failures,
    }
    existing_failures = report.get("failures")
    if not isinstance(existing_failures, list):
        existing_failures = []
    existing_failures.extend(
        f"repository-browser-filter: {failure}" for failure in failures
    )
    report["failures"] = existing_failures
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if failures:
        raise MobileLayoutError(
            "repository browser filter acceptance failed:\n- " + "\n- ".join(failures)
        )


def run_checks(site_root: Path, output_root: Path) -> None:
    core.run_checks(site_root, output_root)
    _run_repository_browser_filter_check(site_root, output_root)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_checks(args.site_root.resolve(strict=True), args.output_root.resolve())
    except (OSError, MobileLayoutError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
