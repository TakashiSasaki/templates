from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_MERGE_SHA = "c5a3294809a1066bf59b83f467f1d597f885289a"
TITLE = "Policy concepts for first-time readers"


def _pages(nodes):
    for node in nodes:
        if "children" in node:
            yield from _pages(node["children"])
        else:
            yield node


class PolicyConceptsPromotionTests(unittest.TestCase):
    def test_policy_concepts_is_promoted_from_exact_policy_revision(self) -> None:
        sources = json.loads(
            (ROOT / "publication-sources.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            POLICY_MERGE_SHA,
            sources["publications"]["policy"]["revision"],
        )

        repository_agent = (ROOT / "agent.json").read_bytes()
        published_agent = (ROOT / "assets/agent.json").read_bytes()
        self.assertEqual(repository_agent, published_agent)
        agent = json.loads(repository_agent.decode("utf-8"))
        self.assertEqual(
            POLICY_MERGE_SHA,
            agent["authorities"]["policy"]["publication_revision"],
        )

        manifest = json.loads(
            (ROOT / "site-manifest.json").read_text(encoding="utf-8")
        )
        policy_pages = [
            page
            for page in _pages(manifest["navigation"])
            if page.get("publication") == "policy"
        ]
        identifiers = [page["document"] for page in policy_pages]
        self.assertEqual(1, identifiers.count("policy-concepts"))
        getting_started = identifiers.index("getting-started")
        self.assertEqual("policy-concepts", identifiers[getting_started + 1])
        concepts = policy_pages[getting_started + 1]
        self.assertEqual(
            {
                "title": TITLE,
                "publication": "policy",
                "document": "policy-concepts",
                "destination": "policy/policy-concepts.md",
            },
            concepts,
        )

        overlays = json.loads(
            (ROOT / "reader-navigation-locales.json").read_text(encoding="utf-8")
        )
        japanese = next(
            locale for locale in overlays["locales"] if locale["language"] == "ja"
        )
        labels = [
            label for label in japanese["labels"] if label["id"] == "policy-concepts"
        ]
        self.assertEqual(
            [
                {
                    "id": "policy-concepts",
                    "canonical": TITLE,
                    "localized": "Policy の概念（初めての読者向け）",
                }
            ],
            labels,
        )

        staging = json.loads(
            (ROOT / "publication-staging.json").read_text(encoding="utf-8")
        )
        historical = [
            mapping
            for mapping in staging["mappings"]
            if mapping["id"] == "policy-concepts"
        ]
        self.assertEqual(1, len(historical))


if __name__ == "__main__":
    unittest.main()
