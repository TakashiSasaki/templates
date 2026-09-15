from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PROMOTION_SHA = "6023af1b6aed4a22407d9ca43106cd66cfee9fb6"
PROMOTED_DOCUMENTS = [
    {
        "document": "contributing",
        "title": "Contributing",
        "destination": "policy/contributing.md",
        "label_id": "contributing",
        "localized": "コントリビューション",
    },
    {
        "document": "maintainer-workflow",
        "title": "Policy maintainer workflow",
        "destination": "policy/policy-maintainer-workflow.md",
        "label_id": "maintainer-workflow",
        "localized": "Policy メンテナワークフロー",
    },
    {
        "document": "adr-review-authority-and-github-runtime-boundary",
        "title": "ADR-0008 Review authority and GitHub runtime boundary",
        "destination": "policy/adr/0008-review-authority-and-github-runtime-boundary.md",
        "label_id": "adr-review-authority",
        "localized": "ADR-0008 レビュー権限と GitHub ランタイム境界",
    },
    {
        "document": "adr-review-result-representation-boundary",
        "title": "ADR-0009 Review result representation boundary",
        "destination": "policy/adr/0009-review-result-representation-boundary.md",
        "label_id": "adr-review-result",
        "localized": "ADR-0009 レビュー結果の表現境界",
    },
]


def _pages(nodes):
    if isinstance(nodes, dict):
        for child in nodes.values():
            if isinstance(child, list):
                yield from _pages(child)
        return
    for node in nodes:
        if "children" in node:
            yield from _pages(node["children"])
        else:
            yield node


class PolicyMaintainerPromotionTests(unittest.TestCase):
    def test_policy_maintainer_documents_promoted_from_exact_policy_revision(self) -> None:
        sources = json.loads(
            (ROOT / "publication-sources.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            POLICY_PROMOTION_SHA,
            sources["publications"]["policy"]["revision"],
        )

        repository_agent = (ROOT / "agent.json").read_bytes()
        published_agent = (ROOT / "assets/agent.json").read_bytes()
        self.assertEqual(repository_agent, published_agent)
        agent = json.loads(repository_agent.decode("utf-8"))
        self.assertEqual(
            POLICY_PROMOTION_SHA,
            agent["authorities"]["policy"]["publication_revision"],
        )

        manifest = json.loads(
            (ROOT / "site-manifest.json").read_text(encoding="utf-8")
        )
        nav_pages = list(_pages(manifest["navigation"]))
        policy_pages_by_doc = {
            page["document"]: page
            for page in nav_pages
            if page.get("publication") == "policy"
        }

        overlays = json.loads(
            (ROOT / "reader-navigation-locales.json").read_text(encoding="utf-8")
        )
        japanese = next(
            locale for locale in overlays["locales"] if locale["language"] == "ja"
        )
        labels_by_id = {
            label["id"]: label for label in japanese["labels"]
        }

        for item in PROMOTED_DOCUMENTS:
            doc_id = item["document"]
            self.assertIn(doc_id, policy_pages_by_doc)
            page = policy_pages_by_doc[doc_id]
            self.assertEqual(item["title"], page["title"])
            self.assertEqual(item["destination"], page["destination"])

            label_id = item["label_id"]
            self.assertIn(label_id, labels_by_id)
            self.assertEqual(item["title"], labels_by_id[label_id]["canonical"])
            self.assertEqual(item["localized"], labels_by_id[label_id]["localized"])

        staging = json.loads(
            (ROOT / "publication-staging.json").read_text(encoding="utf-8")
        )
        staged_ids = {m["id"] for m in staging["mappings"]}
        for item in PROMOTED_DOCUMENTS:
            self.assertNotIn(item["document"], staged_ids)


if __name__ == "__main__":
    unittest.main()
