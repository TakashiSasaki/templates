import unittest
import yaml
from pathlib import Path
from scripts.classify_site_ci import is_site_authority_snapshot

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-pages.yml"


class StackedSiteDocumentationWorkflowTests(unittest.TestCase):
    def test_arbitrary_stacked_site_bases_reach_base_authoritative_classifier(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        events = yaml.safe_load(text)[True]
        self.assertNotIn("branches", events["pull_request"])
        markers = {".github/workflows/build-pages.yml", "scripts/classify_site_ci.py"}
        self.assertTrue(is_site_authority_snapshot(markers))
        self.assertTrue(is_site_authority_snapshot(markers | {"codex/future-stack-base"}))
        self.assertFalse(is_site_authority_snapshot({"integration-source.json"}))
        classifier = (WORKFLOW.parent / "classify.yml").read_text(encoding="utf-8")
        self.assertIn("git ls-tree -r --name-only", classifier)
        self.assertIn("site_candidate", classifier)
        jobs = yaml.safe_load(text)["jobs"]
        for job_name in (
            "build",
            "check",
            "core_tests",
            "validate",
            "policy",
            "website_contract",
            "full_qualification",
            "reference_consumer",
            "cross_authority",
            "explainability",
            "playground",
        ):
            with self.subTest(job=job_name):
                self.assertIn("site_candidate", str(jobs[job_name].get("if", "")))
        self.assertFalse((WORKFLOW.parent / 'build-pages-stacked-site.yml').exists())
        self.assertIn("contents: read", text)
        self.assertNotIn("pages: write", text)
        self.assertNotIn("id-token: write", text)
        self.assertNotIn("actions/deploy-pages", text)
        self.assertNotIn("push:", text)


if __name__ == "__main__":
    unittest.main()
