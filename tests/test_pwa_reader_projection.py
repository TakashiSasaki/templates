from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES = ROOT / "docs" / "capabilities.md"
JAPANESE_CAPABILITIES = ROOT / "translations" / "ja" / "docs" / "capabilities.md"
SITE_MANIFEST = ROOT / "site-manifest.json"


def iter_pages(nodes: list[dict[str, Any]]):
    for node in nodes:
        if "children" in node:
            yield from iter_pages(node["children"])
        else:
            yield node


class PwaReaderProjectionTests(unittest.TestCase):
    def test_pwa_uses_composition_document_without_site_semantic_duplication(self) -> None:
        manifest = json.loads(SITE_MANIFEST.read_text(encoding="utf-8"))
        pages = list(iter_pages(manifest["navigation"]))
        pwa_pages = [
            page
            for page in pages
            if page.get("publication") == "composition"
            and page.get("document") == "pwa-capability"
        ]

        self.assertEqual(
            pwa_pages,
            [
                {
                    "title": "Progressive Web App",
                    "publication": "composition",
                    "document": "pwa-capability",
                    "destination": "capabilities/pwa/index.md",
                }
            ],
        )

        text = CAPABILITIES.read_text(encoding="utf-8")
        self.assertIn("[Browser identity and favicon](../webapp/docs/architecture/contracts/)", text)
        self.assertIn("[Progressive Web App capability](pwa/)", text)
        self.assertIn("Site does not redefine either contract family", text)
        self.assertIn("Composition-owned sources", text)
        self.assertIn("[Policy PWA usage guide](../policy/pwa/)", text)
        self.assertIn("not the reusable application PWA capability authority", text)
        self.assertNotIn("network-first", text)
        self.assertNotIn("cache-first", text)
        self.assertNotIn("Service Worker is required", text)

    def test_japanese_projection_points_to_same_reader_destinations(self) -> None:
        text = JAPANESE_CAPABILITIES.read_text(encoding="utf-8")

        self.assertIn("[Browser identity and favicon](/webapp/docs/architecture/contracts/)", text)
        self.assertIn("[Progressive Web App capability](/capabilities/pwa/)", text)
        self.assertIn("Site はどちらの contract family も再定義せず", text)
        self.assertIn("Composition が所有する正本", text)
        self.assertIn("[Policy PWA usage guide](/policy/pwa/)", text)
        self.assertIn("application PWA capability の authority ではありません", text)


if __name__ == "__main__":
    unittest.main()
