import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-pages-stacked-site.yml"


class StackedSiteDocumentationWorkflowTests(unittest.TestCase):
    def test_stacked_site_wrapper_is_read_only_and_reuses_canonical_build(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('      - "site-*"', text)
        self.assertIn("uses: ./.github/workflows/build-pages.yml", text)
        self.assertIn("site_ref: ${{ github.event.pull_request.head.sha }}", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("pages: write", text)
        self.assertNotIn("id-token: write", text)
        self.assertNotIn("actions/deploy-pages", text)
        self.assertNotIn("push:", text)


if __name__ == "__main__":
    unittest.main()
