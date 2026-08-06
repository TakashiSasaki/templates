from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOCK = ROOT / "publication-sources.json"
SITE_MANIFEST = ROOT / "site-manifest.json"
TREE_PAGE = ROOT / "docs/repository-trees/webapp.md"
DEPLOYMENT_STATE = ROOT / "deployment-state.json"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-pages.yml"
FINAL_WEBAPP_REVISION = "1671c5b503377b87d157aeaa714bdf7c43797dc9"


def navigation_pages(nodes: list[object]) -> dict[tuple[str, str], dict[str, object]]:
    result: dict[tuple[str, str], dict[str, object]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise AssertionError("site navigation nodes must be objects")
        children = node.get("children")
        if children is not None:
            if not isinstance(children, list):
                raise AssertionError("site navigation children must be arrays")
            result.update(navigation_pages(children))
            continue
        publication = node.get("publication")
        document = node.get("document")
        if not isinstance(publication, str) or not isinstance(document, str):
            raise AssertionError("site navigation leaves require publication and document")
        key = (publication, document)
        if key in result:
            raise AssertionError(f"duplicate navigation page: {key}")
        result[key] = node
    return result


class WebappDistributionIntegrationTests(unittest.TestCase):
    def test_site_locks_the_final_reviewed_webapp_revision(self) -> None:
        source_lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))

        self.assertEqual(
            FINAL_WEBAPP_REVISION,
            source_lock["publications"]["webapp"]["revision"],
        )
        self.assertRegex(FINAL_WEBAPP_REVISION, r"\A[0-9a-f]{40}\Z")

    def test_site_navigation_maps_the_new_distribution_documents(self) -> None:
        manifest = json.loads(SITE_MANIFEST.read_text(encoding="utf-8"))
        pages = navigation_pages(manifest["navigation"])

        expected = {
            ("webapp", "distribution-boundary"):
                "webapp/docs/architecture/distribution-boundary.md",
            ("webapp", "distribution-readiness-audit"):
                "webapp/docs/architecture/distribution-readiness-audit.md",
        }
        for key, destination in expected.items():
            with self.subTest(key=key):
                self.assertIn(key, pages)
                self.assertEqual(destination, pages[key]["destination"])

    def test_repository_tree_page_explains_both_artifact_roots(self) -> None:
        page = TREE_PAGE.read_text(encoding="utf-8")

        self.assertIn("template-development source artifact", page)
        self.assertIn("copyable application-template distribution", page)
        self.assertIn("`template/` subtree", page)
        self.assertIn("GENERATED_REPOSITORY_TREE:webapp", page)

    def test_completed_distributions_remain_locked_after_pages_restoration(self) -> None:
        state = json.loads(DEPLOYMENT_STATE.read_text(encoding="utf-8"))
        source_lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
        workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")

        self.assertEqual(
            FINAL_WEBAPP_REVISION,
            source_lock["publications"]["webapp"]["revision"],
        )
        self.assertEqual("active", state["status"])
        self.assertIn("skill", state["reason"])
        self.assertIn("actions/configure-pages@v6", workflow)
        self.assertIn("actions/deploy-pages@v5", workflow)
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("name: github-pages", workflow)
        self.assertIn("github.event_name == 'push'", workflow)
        self.assertIn("github.ref == 'refs/heads/site'", workflow)
        self.assertNotIn("github.event.repository.default_branch", workflow)


if __name__ == "__main__":
    unittest.main()
