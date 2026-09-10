from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "site-composition-materialization-cross-authority.yml"
EXPECTED_COMPOSITION_HEAD = "96bc8a81e2949a17a2c8965fe476c1fd4cba78ac"


class SiteCompositionMaterializationCrossAuthorityWorkflowTests(unittest.TestCase):
    def test_workflow_binds_exact_pr_head_and_c2_head(self) -> None:
        self.assertTrue(WORKFLOW.is_file(), "cross-authority workflow must exist")
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("site_ref: ${{ github.event.pull_request.head.sha }}", text)
        self.assertIn(f"composition_ref: {EXPECTED_COMPOSITION_HEAD}", text)
        self.assertIn('      - "perf/site-*"', text)
        self.assertIn("      - site", text)
        self.assertIn("uses: ./.github/workflows/build-pages.yml", text)


if __name__ == "__main__":
    unittest.main()
