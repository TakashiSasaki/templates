from __future__ import annotations

import unittest
from pathlib import Path

from scripts.check_mobile_layout import (
    CheckCase,
    MobileLayoutError,
    _browser_runtime_arguments,
    harness_html,
    parse_harness_result,
    validate_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/mobile-visual-regression.yml"


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

    def test_landing_preserves_touch_target_floor(self) -> None:
        case = CheckCase("landing", "/", "landing")
        metrics = compact_metrics()
        metrics["cover"] = {"paddingTop": 17}
        metrics["lead"] = {"lineHeight": 25.5}
        metrics["buttons"] = [{"height": 47}, {"height": 48}]
        failures = validate_metrics(case, 390, 844, metrics)
        self.assertIn("portal action 0 is shorter than 48px", failures)

    def test_layout_threshold_exceedance_is_reported(self) -> None:
        case = CheckCase("landing", "/", "landing")
        metrics = compact_metrics()
        metrics["content"] = {"paddingTop": 9}
        metrics["heading"] = {"marginBottom": 23}
        metrics["cover"] = {"paddingTop": 21}
        metrics["lead"] = {"lineHeight": 28}
        metrics["buttons"] = [{"height": 48}]
        failures = validate_metrics(case, 390, 844, metrics)
        self.assertIn("mobile content top padding exceeds 8px", failures)
        self.assertIn("mobile heading bottom margin exceeds 22px", failures)
        self.assertIn("portal cover top padding exceeds 20px", failures)
        self.assertIn("portal lead line height exceeds 27px", failures)

    def test_unready_and_non_numeric_metrics_fail_cleanly(self) -> None:
        case = CheckCase("policy", "/policy/", "document")
        self.assertEqual(
            validate_metrics(
                case,
                390,
                844,
                {"ready": False, "error": "frame failed"},
            ),
            ["harness did not become ready: frame failed"],
        )
        metrics = compact_metrics()
        metrics["viewport"] = {"width": "390", "height": 844}
        self.assertEqual(
            validate_metrics(case, 390, 844, metrics),
            ["viewport.width must be numeric"],
        )

    def test_parse_harness_result_extracts_json_and_rejects_invalid_output(self) -> None:
        parsed = parse_harness_result(
            '<html><pre id="result">{&quot;ready&quot;:true,&quot;value&quot;:1}</pre></html>'
        )
        self.assertEqual(parsed, {"ready": True, "value": 1})

        with self.assertRaisesRegex(MobileLayoutError, "did not contain harness result"):
            parse_harness_result("<html><body>missing</body></html>")
        with self.assertRaisesRegex(MobileLayoutError, "result is not JSON"):
            parse_harness_result('<pre id="result">not-json</pre>')

    def test_harness_keeps_measurement_same_origin(self) -> None:
        text = harness_html()
        self.assertIn('frame.src = target;', text)
        self.assertIn('target.startsWith("/")', text)
        self.assertIn('target.startsWith("//")', text)
        self.assertIn('target.includes("\\\\")', text)
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)

    def test_browser_sandbox_disablement_is_explicit_and_opt_in(self) -> None:
        sandboxed = _browser_runtime_arguments("/tmp/profile", no_sandbox=False)
        unsandboxed = _browser_runtime_arguments("/tmp/profile", no_sandbox=True)
        self.assertNotIn("--no-sandbox", sandboxed)
        self.assertIn("--no-sandbox", unsandboxed)

    def test_workflow_reuses_pages_artifact_and_uploads_visual_evidence(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("actions/github-script@v8", workflow)
        self.assertIn("workflow_id: 'build-pages.yml'", workflow)
        self.assertIn("actions/download-artifact@v5", workflow)
        self.assertIn("browser-actions/setup-chrome@v2", workflow)
        self.assertIn("scripts/check_mobile_layout.py", workflow)
        self.assertIn("--no-sandbox", workflow)
        self.assertIn("build/mobile-visual", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            workflow,
        )
        self.assertNotIn("actions/upload-pages-artifact", workflow)


if __name__ == "__main__":
    unittest.main()
