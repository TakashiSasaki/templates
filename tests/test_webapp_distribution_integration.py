from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOCK = ROOT / "publication-sources.json"
SITE_MANIFEST = ROOT / "site-manifest.json"
TREE_PAGE = ROOT / "docs/repository-trees/webapp.md"
DEPLOYMENT_STATE = ROOT / "deployment-state.json"
FINAL_WEBAPP_REVISION = "1671c5b503377b87d157aeaa714bdf7c43797dc9"
WEBAPP_INTEGRATION_REVISION = "552af87fb32e614072ac195e83514e47feaf5c01"
SITE_PRE_RESTORATION_REVISION = "f372805850848fb4fc05205ebb47d27e5e6b45f6"


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

    def test_active_deployment_is_bound_to_the_integrated_revisions(self) -> None:
        source_lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
        state = json.loads(DEPLOYMENT_STATE.read_text(encoding="utf-8"))

        self.assertEqual("active", state["status"])
        self.assertEqual(
            source_lock["publications"]["webapp"]["revision"],
            state["restored_after"]["webapp_revision"],
        )
        self.assertEqual(
            FINAL_WEBAPP_REVISION,
            state["restored_after"]["webapp_revision"],
        )
        self.assertEqual(
            WEBAPP_INTEGRATION_REVISION,
            state["restored_after"]["webapp_integration_revision"],
        )
        self.assertEqual(
            SITE_PRE_RESTORATION_REVISION,
            state["restored_after"]["site_pre_restoration_revision"],
        )


if __name__ == "__main__":
    unittest.main()
