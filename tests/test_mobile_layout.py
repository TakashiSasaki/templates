from __future__ import annotations

import unittest
from pathlib import Path

from scripts.check_mobile_layout import (
    CASES,
    CheckCase,
    MobileLayoutError,
    _number,
    _validate_cases,
    validate_metrics,
    validate_repository_viewer_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
BUILD_WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
REPLAY_WORKFLOW = ROOT / ".github/workflows/mobile-visual-regression.yml"
VISUAL_REQUIREMENTS = ROOT / "requirements-visual.txt"


def compact_metrics() -> dict:
    return {
        "ready": True,
        "viewport": {"width": 390, "height": 844},
        "page": {"clientWidth": 390, "scrollWidth": 390},
        "content": {"paddingTop": 6},
        "breadcrumb": {"paddingTop": 4},
        "heading": {"marginBottom": 18},
        "cover": None,
        "lead": None,
        "buttons": [],
        "revision": None,
        "revisionTable": None,
    }


def repository_viewer_metrics(show_lines: bool, wrap_lines: bool) -> dict:
    line_number_width = 64 if show_lines else 0
    return {
        "ready": True,
        "viewport": {"width": 390, "height": 844},
        "state": {"showLines": show_lines, "wrapLines": wrap_lines},
        "line": {"left": 0, "width": 390},
        "code": {
            "left": line_number_width,
            "width": 390 - line_number_width,
            "whiteSpace": "pre-wrap" if wrap_lines else "pre",
            "overflowWrap": "anywhere" if wrap_lines else "normal",
            "gridColumnStart": "2" if show_lines else "1",
        },
        "lineNumber": {"display": "block" if show_lines else "none"},
    }


class MobileLayoutRegressionTests(unittest.TestCase):
    def test_document_metrics_accept_compact_mobile_geometry(self) -> None:
        case = CheckCase("policy", "/policy/", "document")
        self.assertEqual(validate_metrics(case, 390, 844, compact_metrics()), [])

    def test_page_wide_horizontal_overflow_is_rejected(self) -> None:
        case = CheckCase("policy", "/policy/", "document")
        metrics = compact_metrics()
        metrics["page"] = {"clientWidth": 390, "scrollWidth": 430}
        failures = validate_metrics(case, 390, 844, metrics)
        self.assertTrue(
            any("page-wide horizontal overflow" in failure for failure in failures)
        )

    def test_repository_revision_must_remain_one_line(self) -> None:
        case = CheckCase(
            "repository-trees",
            "/repository-trees/",
            "repository-table",
        )
        metrics = compact_metrics()
        metrics["revision"] = {
            "text": "a" * 40,
            "height": 22,
            "lineHeight": 22,
            "whiteSpace": "normal",
            "overflowWrap": "normal",
            "wordBreak": "normal",
            "rectCount": 2,
        }
        metrics["revisionTable"] = {"clientWidth": 360, "scrollWidth": 520}
        failures = validate_metrics(case, 390, 844, metrics)
        self.assertIn("repository revision is allowed to wrap", failures)
        self.assertIn("repository revision occupies multiple line boxes", failures)

    def test_repository_viewer_accepts_all_four_control_states(self) -> None:
        for show_lines in (True, False):
            for wrap_lines in (True, False):
                with self.subTest(show_lines=show_lines, wrap_lines=wrap_lines):
                    self.assertEqual(
                        validate_repository_viewer_metrics(
                            390,
                            844,
                            show_lines,
                            wrap_lines,
                            repository_viewer_metrics(show_lines, wrap_lines),
                        ),
                        [],
                    )

    def test_repository_viewer_rejects_collapsed_code_without_line_numbers(self) -> None:
        metrics = repository_viewer_metrics(False, True)
        metrics["code"]["width"] = 28.8
        failures = validate_repository_viewer_metrics(
            390,
            844,
            False,
            True,
            metrics,
        )
        self.assertIn(
            "repository file code does not fill the line when line numbers are hidden",
            failures,
        )

    def test_repository_viewer_requires_explicit_code_grid_column(self) -> None:
        metrics = repository_viewer_metrics(False, True)
        metrics["code"]["gridColumnStart"] = "auto"
        failures = validate_repository_viewer_metrics(
            390,
            844,
            False,
            True,
            metrics,
        )
        self.assertIn(
            "repository file code is not explicitly placed in grid column 1",
            failures,
        )

    def test_repository_viewer_requires_wrap_semantics(self) -> None:
        metrics = repository_viewer_metrics(False, True)
        metrics["code"]["whiteSpace"] = "pre"
        metrics["code"]["overflowWrap"] = "normal"
        failures = validate_repository_viewer_metrics(
            390,
            844,
            False,
            True,
            metrics,
        )
        self.assertIn("repository file wrapping is not pre-wrap", failures)
        self.assertIn("repository file overflow wrapping is not anywhere", failures)

    def test_landing_preserves_touch_target_floor(self) -> None:
        case = CheckCase("landing", "/", "landing")
        metrics = compact_metrics()
        metrics["cover"] = {"paddingTop": 17, "height": 650}
        metrics["lead"] = {"lineHeight": 25.5}
        metrics["buttons"] = [{"height": 47}, {"height": 48}]
        failures = validate_metrics(case, 390, 844, metrics)
        self.assertIn("portal action 0 is shorter than 48px", failures)

    def test_landing_hero_cannot_consume_nearly_the_full_viewport(self) -> None:
        case = CheckCase("landing", "/", "landing")
        metrics = compact_metrics()
        metrics["cover"] = {"paddingTop": 17, "height": 761}
        metrics["lead"] = {"lineHeight": 25.5}
        metrics["buttons"] = [{"height": 48}, {"height": 48}]
        failures = validate_metrics(case, 390, 844, metrics)
        self.assertIn(
            "portal cover consumes more than 90% of the mobile viewport height",
            failures,
        )

    def test_layout_threshold_exceedance_is_reported(self) -> None:
        case = CheckCase("landing", "/", "landing")
        metrics = compact_metrics()
        metrics["content"] = {"paddingTop": 9}
        metrics["heading"] = {"marginBottom": 23}
        metrics["cover"] = {"paddingTop": 21, "height": 650}
        metrics["lead"] = {"lineHeight": 28}
        metrics["buttons"] = [{"height": 48}]
        failures = validate_metrics(case, 390, 844, metrics)
        self.assertIn("mobile content top padding exceeds 8px", failures)
        self.assertIn("mobile heading bottom margin exceeds 22px", failures)
        self.assertIn("portal cover top padding exceeds 20px", failures)
        self.assertIn("portal lead line height exceeds 27px", failures)

    def test_missing_required_elements_are_reported(self) -> None:
        case = CheckCase("policy", "/policy/", "document")
        metrics = compact_metrics()
        metrics["content"] = None
        metrics["heading"] = None
        failures = validate_metrics(case, 390, 844, metrics)
        self.assertIn("missing .md-content__inner", failures)
        self.assertIn("missing visible page heading", failures)

    def test_unready_and_non_numeric_metrics_fail_cleanly(self) -> None:
        case = CheckCase("policy", "/policy/", "document")
        self.assertEqual(
            validate_metrics(
                case,
                390,
                844,
                {"ready": False, "error": "page failed"},
            ),
            ["browser measurement did not become ready: page failed"],
        )
        metrics = compact_metrics()
        metrics["viewport"] = {"width": "390", "height": 844}
        self.assertEqual(
            validate_metrics(case, 390, 844, metrics),
            ["viewport.width must be numeric"],
        )

    def test_number_rejects_boolean_non_numeric_and_infinite_values(self) -> None:
        for value in (True, False, "1", None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(MobileLayoutError, "metric must be numeric"):
                    _number(value, "metric")
        for value in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(MobileLayoutError, "metric must be finite"):
                    _number(value, "metric")

    def test_layout_cases_are_fixed_same_origin_paths(self) -> None:
        _validate_cases()
        self.assertGreaterEqual(len(CASES), 4)
        for case in CASES:
            with self.subTest(case=case.name):
                self.assertTrue(case.path.startswith("/"))
                self.assertFalse(case.path.startswith("//"))
                self.assertNotIn("\\", case.path)

    def test_visual_dependency_is_pinned(self) -> None:
        self.assertEqual(
            VISUAL_REQUIREMENTS.read_text(encoding="utf-8"),
            "playwright==1.61.0\n",
        )

    def test_pr_build_runs_browser_regression_after_its_own_artifact(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
        check_block = workflow.split("\n  check:\n", 1)[1]
        self.assertIn("needs:\n      - build\n      - classify_browser", check_block)
        self.assertIn("test \"$BUILD_RESULT\" = success", check_block)
        self.assertIn("test \"$CLASSIFIER_RESULT\" = success", check_block)
        self.assertIn("inputs.site_ref == ''", check_block)
        self.assertIn("actions/download-artifact@v5", check_block)
        self.assertIn(
            "if: ${{ needs.classify_browser.outputs.required == 'true' }}",
            check_block,
        )
        self.assertNotIn("Wait for documentation artifact build", workflow)
        self.assertNotIn("workflow_id: 'build-pages.yml'", workflow)
        self.assertIn("actions/setup-python@v6", check_block)
        self.assertIn("requirements-visual.txt", check_block)
        self.assertIn("Install Japanese browser font", check_block)
        self.assertIn("sudo apt-get update", check_block)
        self.assertIn(
            "sudo apt-get install --yes --no-install-recommends fonts-ipafont-gothic",
            check_block,
        )
        self.assertIn(
            "python -m playwright install --only-shell chromium",
            check_block,
        )
        self.assertNotIn(
            "python -m playwright install --with-deps --only-shell chromium",
            check_block,
        )
        self.assertIn("scripts/check_mobile_layout.py", check_block)
        self.assertIn("build/mobile-visual", check_block)
        self.assertIn("actions/upload-artifact@v4", check_block)
        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            check_block,
        )
        self.assertNotIn("browser-actions/setup-chrome", workflow)
        self.assertNotIn("--no-sandbox", workflow)

    def test_manual_replay_uses_explicit_build_run_without_polling(self) -> None:
        workflow = REPLAY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("run-id: ${{ inputs.run_id }}", workflow)
        self.assertIn("github-token: ${{ github.token }}", workflow)
        self.assertIn(
            "python -m playwright install --with-deps --only-shell chromium",
            workflow,
        )
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("actions/github-script@v8", workflow)
        self.assertNotIn("workflow_id: 'build-pages.yml'", workflow)
        self.assertNotIn("Wait for documentation artifact build", workflow)
        self.assertNotIn("actions/upload-pages-artifact", workflow)


if __name__ == "__main__":
    unittest.main()
