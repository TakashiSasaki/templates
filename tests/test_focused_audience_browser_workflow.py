from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "audience-browser-focused.yml"


class FocusedAudienceBrowserWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_lane_is_harness_only_and_base_artifact_bound(self) -> None:
        self.assertIn("scripts/check_audience_*.py", self.text)
        self.assertIn("tests/test_check_audience_*.py", self.text)
        self.assertIn("github.event.pull_request.base.sha", self.text)
        self.assertIn("harness-only audience browser change", self.text)
        self.assertIn("diff includes product/build/CI-control paths", self.text)

    def test_lane_reuses_artifact_without_running_site_producer(self) -> None:
        self.assertIn("python scripts/fetch_base_site_artifact.py", self.text)
        self.assertIn("python scripts/check_audience_artifact.py", self.text)
        self.assertIn("python scripts/check_audience_runtime.py", self.text)
        self.assertNotIn("site-producer.yml", self.text)
        self.assertNotIn("playwright install --only-shell", self.text)
        self.assertNotIn("apt-get install", self.text)

    def test_missing_artifact_defers_to_canonical_ci_without_claiming_acceptance(self) -> None:
        self.assertIn('if [ "$status" -eq 3 ]', self.text)
        self.assertIn("canonical CI remains authoritative", self.text)
        self.assertIn("diagnostic evidence only", self.text)
        self.assertIn("does not replace exact-head canonical qualification", self.text)

    def test_artifact_corruption_is_not_swallowed(self) -> None:
        self.assertIn('exit "$status"', self.text)
        self.assertIn("actions: read", self.text)
        self.assertIn("Focused audience browser / validate", self.text)


if __name__ == "__main__":
    unittest.main()
