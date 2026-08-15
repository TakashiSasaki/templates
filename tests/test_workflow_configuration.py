from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_WORKFLOW_PATH = ROOT / ".github/workflows/contract-validation.yml"
SITE_COMPATIBILITY_WORKFLOW_PATH = ROOT / ".github/workflows/site-compatibility.yml"
PINNED_SITE_SHA = "4af6fd6989cfff1ec11ab5da6e9bd79ec38b51fd"


class WorkflowConfigurationTests(unittest.TestCase):
    def test_contract_validation_is_not_restricted_to_template_source_branches(self) -> None:
        workflow = CONTRACT_WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("on:\n  push:\n  pull_request:\n", workflow)
        self.assertNotIn("branches:", workflow)
        self.assertNotIn("branches-ignore:", workflow)

    def test_site_compatibility_workflow_uses_reviewed_immutable_site_revision(self) -> None:
        workflow = SITE_COMPATIBILITY_WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("branches:\n      - webapp", workflow)
        self.assertIn("- docs/**", workflow)
        self.assertIn("- template/**", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn(
            f"uses: TakashiSasaki/templates/.github/workflows/build-pages.yml@{PINNED_SITE_SHA}",
            workflow,
        )
        self.assertIn(f"site_ref: {PINNED_SITE_SHA}", workflow)
        self.assertIn("webapp_ref: ${{ github.sha }}", workflow)
        self.assertNotIn("build-pages.yml@site", workflow)
        self.assertNotRegex(workflow, r"webapp_ref:\s*webapp\b")
        self.assertRegex(PINNED_SITE_SHA, re.compile(r"\A[0-9a-f]{40}\Z"))


if __name__ == "__main__":
    unittest.main()
