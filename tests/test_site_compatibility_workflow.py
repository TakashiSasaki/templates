from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/site-compatibility.yml"
PINNED_SITE_SHA = "4af6fd6989cfff1ec11ab5da6e9bd79ec38b51fd"


class SiteCompatibilityWorkflowTests(unittest.TestCase):
    def test_policy_workflow_uses_reviewed_immutable_site_revision(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("branches:\n      - policy", text)
        self.assertIn("- docs/**", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn(
            f"uses: TakashiSasaki/templates/.github/workflows/build-pages.yml@{PINNED_SITE_SHA}",
            text,
        )
        self.assertIn(f"site_ref: {PINNED_SITE_SHA}", text)
        self.assertIn("policy_ref: ${{ github.sha }}", text)
        self.assertNotIn("build-pages.yml@site", text)
        self.assertNotRegex(text, r"policy_ref:\s*policy\b")
        self.assertRegex(PINNED_SITE_SHA, re.compile(r"\A[0-9a-f]{40}\Z"))


if __name__ == "__main__":
    unittest.main()
