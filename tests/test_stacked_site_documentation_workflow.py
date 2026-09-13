import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-pages.yml"


class StackedSiteDocumentationWorkflowTests(unittest.TestCase):
    def test_stacked_site_bases_use_one_read_only_canonical_build(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("      - 'site-*'", text)
        self.assertIn("      - 'perf/site-*'", text)
        self.assertIn("      - 'feat/site-*'", text)
        self.assertFalse((WORKFLOW.parent / 'build-pages-stacked-site.yml').exists())
        self.assertIn("contents: read", text)
        self.assertNotIn("pages: write", text)
        self.assertNotIn("id-token: write", text)
        self.assertNotIn("actions/deploy-pages", text)
        self.assertNotIn("push:", text)


if __name__ == "__main__":
    unittest.main()
