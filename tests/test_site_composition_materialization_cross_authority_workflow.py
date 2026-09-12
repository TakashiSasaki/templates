from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "site-composition-materialization-cross-authority.yml"
EXPECTED_COMPOSITION_HEAD = "4d7e98be157acb20c9be732df48158e4a588b272"


class SiteCompositionMaterializationCrossAuthorityWorkflowTests(unittest.TestCase):
    def test_workflow_binds_exact_pr_head_and_c2_head(self) -> None:
        self.assertTrue(WORKFLOW.is_file(), "cross-authority workflow must exist")
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("site_ref: ${{ github.event.pull_request.head.sha }}", text)
        self.assertIn(f"composition_ref: {EXPECTED_COMPOSITION_HEAD}", text)
        self.assertIn('      - "perf/site-*"', text)
        self.assertIn("      - site", text)
        self.assertIn("uses: ./.github/workflows/build-pages.yml", text)

    def test_build_pages_materializes_before_site_assembly_tests(self) -> None:
        workflow = ROOT / ".github" / "workflows" / "build-pages.yml"
        self.assertTrue(workflow.is_file(), "reusable Pages workflow must exist")
        text = workflow.read_text(encoding="utf-8")
        materialize = "      - name: Materialize provider publications\n"
        assembly_tests = "      - name: Run site assembly tests\n"
        self.assertEqual(1, text.count(materialize), "materialization phase must be unique")
        self.assertEqual(1, text.count(assembly_tests), "site assembly test phase must be unique")
        self.assertLess(
            text.index(materialize),
            text.index(assembly_tests),
            "provider materialization must precede test discovery so CI cannot silently skip unmaterialized provider integrations",
        )


if __name__ == "__main__":
    unittest.main()
