from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check_pwa_commit_regressions.py"
WORKFLOW = ROOT / ".github/workflows/mobile-visual-regression.yml"


class PwaCommitRegressionTests(unittest.TestCase):
    def test_checker_covers_commit_and_cache_order_regressions(self) -> None:
        source = CHECKER.read_text(encoding="utf-8")
        self.assertIn('evidence["same_url_fresh_retry_cleared_on_commit"] = True', source)
        self.assertIn('evidence["full_navigation_commit_retained_warning"] = True', source)
        self.assertIn('evidence["standalone_inline_warning_style"] = True', source)
        self.assertIn('evidence["older_200_did_not_resurrect_after_newer_404"] = True', source)
        self.assertIn("globalThis.__pwaFixtureCommitDocument('/document/')", source)
        self.assertIn('data-templates-cached-fallback', source)
        self.assertIn("getComputedStyle(element).position", source)
        self.assertIn("state.begin_race()", source)
        self.assertIn("setTimeout(resolve, 50)", source)
        self.assertIn("[200, 404]", source)

    def test_mobile_visual_workflow_runs_commit_checker(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Check PWA document commit correlation", workflow)
        self.assertIn("python scripts/check_pwa_commit_regressions.py", workflow)
        self.assertIn("build/mobile-visual/pwa-document-commit.json", workflow)


if __name__ == "__main__":
    unittest.main()
