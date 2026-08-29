#!/usr/bin/env python3
"""Same-artifact Chromium acceptance for repository-browser file filtering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from scripts import check_mobile_layout_core as core
except ModuleNotFoundError:
    import check_mobile_layout_core as core


MobileLayoutError = core.MobileLayoutError
_number = core._number

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
        filtered_exposed = int(
            _number(filtered.get("exposed"), "filter filtered.exposed")
        )
        saved_scroll = _number(filtered.get("scrollTop"), "filter filtered.scrollTop")
        returned_scroll = _number(
            returned.get("scrollTop"), "filter returned.scrollTop"
        )
        zero_exposed = int(_number(zero.get("exposed"), "filter zero.exposed"))
        cleared_exposed = int(
            _number(cleared.get("exposed"), "filter cleared.exposed")
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
    if filtered_exposed < 1 or filtered_exposed > total:
        failures.append("repository browser filtered result count is invalid")
    if filtered.get("status") != f"{filtered_exposed} of {total} files":
        failures.append("repository browser filtered status count is inconsistent")
    if filtered.get("allMatch") is not True:
        failures.append("repository browser exposes a file that does not match the query")
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

    if zero_exposed != 0 or zero.get("status") != "No matching files":
        failures.append("repository browser zero-result state is not explicit")
    if cleared.get("inputValue") != "":
        failures.append("repository browser Escape did not clear the filter")
    if cleared_exposed != total:
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


def _filter_exposed_repository_paths(page: Any) -> list[str]:
    """Return paths not suppressed by filter-owned ``hidden`` state.

    This intentionally ignores visibility caused by a closed ``<details>``.
    Clearing a filter must restore the pre-filter disclosure state, not force
    every directory open merely to make all descendants match ``:visible``.
    """

    paths = page.locator("a[data-repository-file]").evaluate_all(
        """
        elements => elements
          .filter(element => {
            let current = element;
            while (current) {
              if (current.hidden) return false;
              current = current.parentElement;
            }
            return true;
          })
          .map(element => element.dataset.filePath)
        """
    )
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise MobileLayoutError(
            "repository browser returned invalid filter-exposed file paths"
        )
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
        filtered_paths = _filter_exposed_repository_paths(page)
        filtered_status = filter_status.text_content() or ""
        query_key = query.lower()
        ancestors_open = file_links.evaluate_all(
            """
            (elements, targetPath) => {
              const element = elements.find(candidate => candidate.dataset.filePath === targetPath);
              if (!element) return false;
              let current = element.parentElement;
              while (current) {
                if (current.tagName === "DETAILS" && !current.open) return false;
                current = current.parentElement;
              }
              return true;
            }
            """,
            target_path,
        )

        # Use a broad non-empty query for the mobile context round trip so Enter
        # still has a deterministic first match while the tree remains large
        # enough to exercise scroll restoration.
        broad_query = "."
        filter_input.fill(broad_query)
        page.wait_for_timeout(50)
        broad_paths = _filter_exposed_repository_paths(page)
        if not broad_paths:
            broad_query = target_path
            filter_input.fill(broad_query)
            page.wait_for_timeout(50)
            broad_paths = _filter_exposed_repository_paths(page)
        tree_scroller = page.locator(".tree")
        saved_scroll = tree_scroller.evaluate(
            "element => { const value = Math.min(137, Math.max(0, element.scrollHeight - element.clientHeight)); "
            "element.scrollTop = value; return element.scrollTop; }"
        )
        filtered = {
            "query": query,
            "exposed": len(filtered_paths),
            "allMatch": all(query_key in path.lower() for path in filtered_paths),
            "ancestorsOpen": bool(ancestors_open),
            "status": filtered_status,
            "broadQuery": broad_query,
            "broadExposed": len(broad_paths),
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
            "exposed": len(_filter_exposed_repository_paths(page)),
            "status": filter_status.text_content() or "",
        }
        filter_input.press("Escape")
        page.wait_for_timeout(50)
        details_after = page.locator(".tree details").evaluate_all(
            "elements => elements.map(element => element.open)"
        )
        cleared = {
            "exposed": len(_filter_exposed_repository_paths(page)),
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
            "viewport": {
                "width": page.evaluate("() => innerWidth"),
                "height": page.evaluate("() => innerHeight"),
            },
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


def run_repository_browser_filter_check(
    site_root: Path,
    output_root: Path,
) -> None:
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
