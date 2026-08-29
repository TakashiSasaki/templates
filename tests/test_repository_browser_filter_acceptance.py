from __future__ import annotations

import unittest

from scripts.check_mobile_layout import (
    REPOSITORY_BROWSER_FILTER_VIEWPORT,
    validate_repository_browser_filter_metrics,
)


def good_metrics() -> dict:
    width, height = REPOSITORY_BROWSER_FILTER_VIEWPORT
    return {
        "ready": True,
        "viewport": {"width": width, "height": height},
        "page": {"clientWidth": width, "scrollWidth": width},
        "initial": {"total": 24, "status": "24 files"},
        "filtered": {
            "query": "DOCS/gUIDE.PY",
            "visible": 1,
            "allMatch": True,
            "ancestorsOpen": True,
            "status": "1 of 24 files",
            "broadQuery": ".",
            "broadVisible": 20,
            "scrollTop": 137,
        },
        "opened": {
            "mobileView": "content",
            "selectedPath": "docs/guide.py",
            "hashPath": "docs/guide.py",
            "frameSrc": "http://127.0.0.1:1234/files/site/content/abcdef.html",
            "filterValue": ".",
            "filesFocused": True,
        },
        "returned": {
            "mobileView": "files",
            "filterValue": ".",
            "scrollTop": 137,
            "filterFocused": True,
        },
        "slash": {
            "mobileView": "files",
            "filterValue": ".",
            "filterFocused": True,
        },
        "zero": {"visible": 0, "status": "No matching files"},
        "cleared": {
            "visible": 24,
            "inputValue": "",
            "detailsRestored": True,
            "status": "24 files",
        },
    }


class RepositoryBrowserFilterAcceptanceTests(unittest.TestCase):
    def test_accepts_complete_repository_filter_round_trip(self) -> None:
        self.assertEqual(validate_repository_browser_filter_metrics(good_metrics()), [])

    def test_rejects_context_and_zero_state_regressions(self) -> None:
        metrics = good_metrics()
        metrics["returned"]["scrollTop"] = 0
        metrics["returned"]["filterFocused"] = False
        metrics["zero"] = {"visible": 1, "status": "1 of 24 files"}
        failures = validate_repository_browser_filter_metrics(metrics)
        self.assertIn(
            "repository browser Files return did not restore tree scroll",
            failures,
        )
        self.assertIn(
            "repository browser Files return did not restore filter focus",
            failures,
        )
        self.assertIn(
            "repository browser zero-result state is not explicit",
            failures,
        )

    def test_rejects_selection_url_and_clear_state_regressions(self) -> None:
        metrics = good_metrics()
        metrics["opened"]["hashPath"] = "other.py"
        metrics["opened"]["frameSrc"] = "https://github.com/example/repo/blob/x/file.py"
        metrics["cleared"]["detailsRestored"] = False
        failures = validate_repository_browser_filter_metrics(metrics)
        self.assertIn(
            "repository browser quick-open URL does not match the selection",
            failures,
        )
        self.assertIn(
            "repository browser quick-open did not load a bounded viewer URL",
            failures,
        )
        self.assertIn(
            "repository browser clear did not restore directory open state",
            failures,
        )

    def test_unready_metrics_fail_closed(self) -> None:
        self.assertEqual(
            validate_repository_browser_filter_metrics(
                {"ready": False, "error": "filter missing"}
            ),
            [
                "repository browser filter measurement did not become ready: filter missing"
            ],
        )


if __name__ == "__main__":
    unittest.main()
