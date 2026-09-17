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
)


ROOT = Path(__file__).resolve().parents[1]
BUILD_WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
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
        self.assertGreaterEqual(len(CASES), 3)
        for case in CASES:
            with self.subTest(case=case.name):
                self.assertTrue(case.path.startswith("/"))
                self.assertFalse(case.path.startswith("//"))
                self.assertNotIn("\\", case.path)

    def test_visual_dependency_is_pinned(self) -> None:
        self.assertEqual(
            VISUAL_REQUIREMENTS.read_text(encoding="utf-8"),
            "playwright==1.61.0\nPygments==2.20.0\nPyYAML==6.0.3\n",
        )

    def test_pr_build_runs_browser_regression_after_its_own_artifact(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
        check_block = workflow.split("\n  check:\n", 1)[1]
        self.assertIn("needs:\n      - build\n      - classify_browser", check_block)
        self.assertIn("test \"$BUILD_RESULT\" = success", check_block)
        self.assertIn("test \"$CLASSIFIER_RESULT\" = success", check_block)
        self.assertIn("inputs.site_ref == ''", check_block)
        self.assertIn("scripts/consume_site_build_artifact.py", check_block)
        self.assertIn(
            "if: ${{ needs.classify_browser.outputs.browser_required == 'true' }}",
            check_block,
        )
        self.assertNotIn("Wait for documentation artifact build", workflow)
        self.assertNotIn("workflow_id: 'build-pages.yml'", workflow)
        self.assertNotIn("actions/setup-python", check_block)
        self.assertIn("requirements-visual.txt", check_block)
        self.assertIn("Install Japanese browser font", check_block)
        self.assertIn("sudo apt-get update", check_block)
        self.assertIn(
            "sudo apt-get install --yes --no-install-recommends fonts-ipafont-gothic",
            check_block,
        )
        self.assertIn(
            "python3 -m playwright install --only-shell chromium",
            check_block,
        )
        self.assertNotIn(
            "python3 -m playwright install --with-deps --only-shell chromium",
            check_block,
        )
        self.assertIn("build/mobile-visual", check_block)
        self.assertIn("actions/upload-artifact@v4", check_block)
        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            check_block,
        )
        self.assertNotIn("browser-actions/setup-chrome", workflow)
        self.assertNotIn("--no-sandbox", workflow)

if __name__ == "__main__":
    unittest.main()
