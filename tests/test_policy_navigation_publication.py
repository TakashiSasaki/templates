from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _walk_navigation(items: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(items, dict):
        leaves: list[dict[str, Any]] = []
        for child in items.values():
            if isinstance(child, list):
                leaves.extend(_walk_navigation(child))
        return leaves
    leaves: list[dict[str, Any]] = []
    for item in items:
        children = item.get("children")
        if isinstance(children, list):
            leaves.extend(_walk_navigation(children))
        else:
            leaves.append(item)
    return leaves


class PolicyNavigationPublicationTests(unittest.TestCase):
    def test_site_pins_policy_navigation_to_immutable_revision(self) -> None:
        lock = json.loads(
            (ROOT / "publication-sources.json").read_text(encoding="utf-8")
        )
        policy = lock["publications"]["policy"]

        self.assertEqual(set(policy), {"revision"})
        self.assertRegex(policy["revision"], r"\A[0-9a-f]{40}\Z")

    def test_site_publishes_policy_layer_navigation_documents(self) -> None:
        manifest = json.loads(
            (ROOT / "site-manifest.json").read_text(encoding="utf-8")
        )
        if manifest.get("schema_version") == 3:
            policy_items = [
                item for item in manifest["documents"] if item.get("publication") == "policy"
            ]
        else:
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
            "policy-profiles": (
                "Policy profiles",
                "policy/shared-policy/profiles.md",
            ),
            "adr-single-agent-policy-skill-runtime-cache": (
                "ADR-0007 Single agent-policy skill runtime cache",
                "policy/adr/0007-single-agent-policy-skill-runtime-cache.md",
            ),
            "adr-integrated-bootstrap-skill": (
                "ADR-0004 Integrated bootstrap skill (superseded)",
                "policy/adr/0004-integrated-bootstrap-skill.md",
            ),
        }
        for document_id, (title, destination) in expected.items():
            with self.subTest(document_id=document_id):
                item = policy_documents[document_id]
                self.assertEqual(item["title"], title)
                self.assertEqual(item["destination"], destination)

        if manifest.get("schema_version") == 3:
            maintain_nav = manifest["navigation"]["maintain"]
            authorities = next(node for node in maintain_nav if node["title"] == "Authorities")
            policy_section = next(child for child in authorities["children"] if child["title"] == "Policy")
            policy_section_docs = [c["document"] for c in policy_section["children"]]
            self.assertIn("provider-navigation", policy_section_docs)
            self.assertIn("shared-policy-navigation", policy_section_docs)

            use_nav = manifest["navigation"]["use"]
            policy_use = next(node for node in use_nav if node["title"] == "Policy")
            policy_use_docs = [c["document"] for c in _walk_navigation(policy_use["children"])]
            self.assertIn("consumer-policy-navigation", policy_use_docs)

            configuration_index = policy_section_docs.index("configuration")
            self.assertEqual(
                policy_section_docs[configuration_index : configuration_index + 3],
                ["configuration", "policy-profiles", "policy-authoring"],
            )

            adr_section = next(node for node in maintain_nav if node["title"] == "Architecture decisions")
            adr_node = next(child for child in adr_section["children"] if child["title"] == "Policy")
            self.assertEqual(
                [child["document"] for child in adr_node["children"]],
                [
                    "adr-index",
                    "adr-repository-adoption",
                    "adr-application-neutral-scope",
                    "adr-single-policy-authority",
                    "adr-copyable-artifact-policy-adoption",
                    "adr-single-agent-policy-skill-runtime-cache",
                    "adr-review-authority-and-github-runtime-boundary",
                    "adr-review-result-representation-boundary",
                ],
            )
            return

        policy_section = next(
            node for node in manifest["navigation"] if node["title"] == "Policy"
        )
        layers_node = next(
            child
            for child in policy_section["children"]
            if child.get("title") == "Policy layers"
        )
        self.assertEqual(
            [
                (
                    child["title"],
                    child["document"],
                    child["destination"],
                )
                for child in layers_node["children"]
            ],
            [
                (
                    "Provider and toolchain",
                    "provider-navigation",
                    "policy/provider/index.md",
                ),
                (
                    "Shared policy corpus",
                    "shared-policy-navigation",
                    "policy/shared-policy/index.md",
                ),
                (
                    "Consumer effective policy",
                    "consumer-policy-navigation",
                    "policy/consumer/index.md",
                ),
            ],
        )

        design_node = next(
            child
            for child in policy_section["children"]
            if child.get("title") == "Design"
        )
        design_documents = [child["document"] for child in design_node["children"]]
        configuration_index = design_documents.index("configuration")
        self.assertEqual(
            design_documents[configuration_index : configuration_index + 3],
            ["configuration", "policy-profiles", "policy-authoring"],
        )

        adr_node = next(
            child
            for child in policy_section["children"]
            if child["title"] == "Architecture decisions"
        )
        self.assertEqual(adr_node["children"][0]["document"], "adr-index")
        current = next(
            child
            for child in adr_node["children"]
            if child.get("title") == "Current decisions"
        )
        superseded = next(
            child
            for child in adr_node["children"]
            if child.get("title") == "Superseded decisions"
        )
        self.assertEqual(
            [child["document"] for child in current["children"]],
            [
                "adr-repository-adoption",
                "adr-application-neutral-scope",
                "adr-single-policy-authority",
                "adr-copyable-artifact-policy-adoption",
                "adr-single-agent-policy-skill-runtime-cache",
                "adr-review-authority-and-github-runtime-boundary",
                "adr-review-result-representation-boundary",
            ],
        )
        self.assertEqual(
            [child["document"] for child in superseded["children"]],
            ["adr-integrated-bootstrap-skill"],
        )

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
