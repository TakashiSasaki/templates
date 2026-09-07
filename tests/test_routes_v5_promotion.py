from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSITION_MERGE_SHA = "806f8574a8b9607c5d6cf438f96e5801ea69f7ae"
COMPOSITION_CONSUMER_SHA = "bd28b67ad97652182d6744ee38ef992349104961"
TITLE = "Routes v4 to v5"
DOCUMENT = "web-routes-v4-migration"
DESTINATION = "web/migrations/routes-v4-to-v5.md"
ROUTE_ID = "composition-web-routes-v4-migration"


def _pages(nodes):
    for node in nodes:
        if "children" in node:
            yield from _pages(node["children"])
        else:
            yield node


class RoutesV5PromotionTests(unittest.TestCase):
    def test_routes_v5_is_promoted_from_exact_composition_revision(self) -> None:
        sources = json.loads(
            (ROOT / "publication-sources.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            COMPOSITION_MERGE_SHA,
            sources["publications"]["composition"]["revision"],
        )

        lock = json.loads(
            (ROOT / ".template-composition/lock.json").read_text(encoding="utf-8")
        )
        self.assertEqual(COMPOSITION_CONSUMER_SHA, lock["source"]["revision"])
        self.assertNotEqual(
            sources["publications"]["composition"]["revision"],
            lock["source"]["revision"],
        )

        repository_agent = (ROOT / "agent.json").read_bytes()
        published_agent = (ROOT / "assets/agent.json").read_bytes()
        self.assertEqual(repository_agent, published_agent)
        agent = json.loads(repository_agent.decode("utf-8"))
        self.assertEqual(
            COMPOSITION_MERGE_SHA,
            agent["authorities"]["composition"]["publication_revision"],
        )

        manifest = json.loads(
            (ROOT / "site-manifest.json").read_text(encoding="utf-8")
        )
        composition_pages = [
            page
            for page in _pages(manifest["navigation"])
            if page.get("publication") == "composition"
        ]
        identifiers = [page["document"] for page in composition_pages]
        self.assertEqual(1, identifiers.count(DOCUMENT))
        previous = identifiers.index("web-routes-v3-migration")
        self.assertEqual(DOCUMENT, identifiers[previous + 1])
        self.assertEqual(
            {
                "title": TITLE,
                "publication": "composition",
                "document": DOCUMENT,
                "destination": DESTINATION,
            },
            composition_pages[previous + 1],
        )

        overlays = json.loads(
            (ROOT / "reader-navigation-locales.json").read_text(encoding="utf-8")
        )
        japanese = next(
            locale for locale in overlays["locales"] if locale["language"] == "ja"
        )
        labels = [
            label for label in japanese["labels"] if label["id"] == "routes-v4-to-v5"
        ]
        self.assertEqual(
            [
                {
                    "id": "routes-v4-to-v5",
                    "canonical": TITLE,
                    "localized": "Routes v4 から v5 への移行",
                }
            ],
            labels,
        )

        staging = json.loads(
            (ROOT / "publication-staging.json").read_text(encoding="utf-8")
        )
        historical = [
            mapping for mapping in staging["mappings"] if mapping["id"] == "routes-v5"
        ]
        self.assertEqual(1, len(historical))
        mapping = historical[0]
        self.assertEqual("composition", mapping["publication"])
        self.assertEqual(DOCUMENT, mapping["document"])
        self.assertEqual(TITLE, mapping["title"])
        self.assertEqual(DESTINATION, mapping["destination"])

        routes = json.loads((ROOT / "contracts/routes.json").read_text(encoding="utf-8"))
        route = next(item for item in routes["routes"] if item["id"] == ROUTE_ID)
        self.assertEqual("/web/migrations/routes-v4-to-v5/", route["path"])


if __name__ == "__main__":
    unittest.main()
