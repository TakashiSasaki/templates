from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/composition-unittest-timing-report.yml"


class CompositionUnittestTimingWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow_text = WORKFLOW.read_text(encoding="utf-8")
        self.workflow = yaml.load(self.workflow_text, Loader=yaml.BaseLoader)
        self.assertIsInstance(self.workflow, dict)

    def test_trigger_is_scoped_and_permissions_are_read_only(self) -> None:
        triggers = self.workflow["on"]
        pull_request = triggers["pull_request"]

        self.assertEqual(["site"], pull_request["branches"])
        self.assertEqual(
            {
                ".github/workflows/composition-unittest-timing-report.yml",
                "scripts/report_composition_unittest_timing.py",
                "tests/test_composition_unittest_timing*.py",
            },
            set(pull_request["paths"]),
        )
        self.assertIn("workflow_dispatch", triggers)
        self.assertEqual(
            {"contents": "read", "actions": "read"},
            self.workflow["permissions"],
        )
        self.assertNotIn("contents: write", self.workflow_text)
        self.assertNotIn("pages: write", self.workflow_text)
        self.assertNotIn("id-token: write", self.workflow_text)

    def test_self_test_checks_out_exact_pull_request_head(self) -> None:
        steps = self.workflow["jobs"]["report"]["steps"]
        checkout = next(
            step for step in steps if step["name"] == "Check out Site report implementation"
        )

        self.assertEqual("actions/checkout@v7", checkout["uses"])
        self.assertEqual(
            "${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.ref }}",
            checkout["with"]["ref"],
        )

    def test_canonical_run_discovery_is_bounded_and_paginated(self) -> None:
        steps = self.workflow["jobs"]["report"]["steps"]
        download = next(
            step
            for step in steps
            if step["name"] == "Download recent canonical Composition core logs"
        )
        self.assertEqual("actions/github-script@v8", download["uses"])
        script = download["with"]["script"]

        self.assertIn("const workflowName = 'Composition schema validation';", script)
        self.assertIn("const branch = 'composition';", script)
        self.assertIn("const maxRunPages = 5;", script)
        self.assertIn("page <= maxRunPages && selectedRuns.length < runsToSample", script)
        self.assertIn("listWorkflowRunsForRepo", script)
        self.assertIn("status: 'completed'", script)
        self.assertIn("per_page: 100", script)
        self.assertIn("page,", script)
        self.assertIn("run.head_branch === branch", script)
        self.assertIn("run.conclusion === 'success'", script)
        self.assertIn("response.data.workflow_runs.length < 100", script)
        self.assertIn("max_repository_run_pages: maxRunPages", script)

    def test_report_still_uses_isolated_python_and_artifact_output(self) -> None:
        steps = self.workflow["jobs"]["report"]["steps"]
        aggregate = next(
            step
            for step in steps
            if step["name"] == "Validate and aggregate unittest timing telemetry"
        )
        upload = next(
            step
            for step in steps
            if step["name"] == "Upload machine-readable unittest timing report"
        )

        self.assertIn("python -I scripts/report_composition_unittest_timing.py", aggregate["run"])
        self.assertEqual("actions/upload-artifact@v4", upload["uses"])
        self.assertEqual(
            "composition-unittest-timing-report-${{ github.run_id }}",
            upload["with"]["name"],
        )
        self.assertEqual("30", upload["with"]["retention-days"])


if __name__ == "__main__":
    unittest.main()
