from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_REVISION = "29dba8295b10c1706f78a8c09c61151051d30ee8"


def _walk_navigation(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    leaves: list[dict[str, Any]] = []
    for item in items:
        children = item.get("children")
        if isinstance(children, list):
            leaves.extend(_walk_navigation(children))
        else:
            leaves.append(item)
    return leaves


class PolicyNavigationPublicationTests(unittest.TestCase):
    def test_site_pins_reviewed_policy_navigation_revision(self) -> None:
        lock = json.loads(
            (ROOT / "publication-sources.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            lock["publications"]["policy"]["revision"],
            POLICY_REVISION,
        )

    def test_site_publishes_policy_layer_navigation_documents(self) -> None:
        manifest = json.loads(
            (ROOT / "site-manifest.json").read_text(encoding="utf-8")
        )
        leaves = _walk_navigation(manifest["navigation"])
        policy_items = [
            item for item in leaves if item.get("publication") == "policy"
        ]
        document_ids = [item["document"] for item in policy_items]
        self.assertEqual(len(document_ids), len(set(document_ids)))
        policy_documents = {item["document"]: item for item in policy_items}

        expected = {
            "provider-navigation": (
                "Provider and toolchain",
                "policy/provider/index.md",
            ),
            "shared-policy-navigation": (
                "Shared policy corpus",
                "policy/shared-policy/index.md",
            ),
            "consumer-policy-navigation": (
                "Consumer effective policy",
                "policy/consumer/index.md",
            ),
        }
        for document_id, (title, destination) in expected.items():
            with self.subTest(document_id=document_id):
                item = policy_documents[document_id]
                self.assertEqual(item["title"], title)
                self.assertEqual(item["destination"], destination)

        policy_section = next(
            node for node in manifest["navigation"] if node["title"] == "Policy"
        )
        section_titles = [
            child["title"]
            for child in policy_section["children"]
            if "children" in child
        ]
        self.assertIn("Policy layers", section_titles)

    def test_policy_layer_documents_have_distinct_destinations(self) -> None:
        manifest = json.loads(
            (ROOT / "site-manifest.json").read_text(encoding="utf-8")
        )
        leaves = _walk_navigation(manifest["navigation"])
        destinations = {
            item["destination"]
            for item in leaves
            if item.get("document")
            in {
                "provider-navigation",
                "shared-policy-navigation",
                "consumer-policy-navigation",
            }
        }

        self.assertEqual(
            destinations,
            {
                "policy/provider/index.md",
                "policy/shared-policy/index.md",
                "policy/consumer/index.md",
            },
        )


if __name__ == "__main__":
    unittest.main()
