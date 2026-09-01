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
    def test_pwa_uses_composition_documents_without_site_semantic_duplication(self) -> None:
        manifest = json.loads(SITE_MANIFEST.read_text(encoding="utf-8"))
        pages = list(iter_pages(manifest["navigation"]))
        pwa_pages = [
            page
            for page in pages
            if page.get("publication") == "composition"
            and page.get("document")
            in {"pwa-capability", "pwa-offline-v2-migration", "pwa-update-v2-migration"}
        ]

        self.assertEqual(
            pwa_pages,
            [
                {
                    "title": "Progressive Web App",
                    "publication": "composition",
                    "document": "pwa-capability",
                    "destination": "capabilities/pwa/index.md",
                },
                {
                    "title": "PWA offline v1 to v2",
                    "publication": "composition",
                    "document": "pwa-offline-v2-migration",
                    "destination": "capabilities/pwa/migrations/offline-v1-to-v2.md",
                },
                {
                    "title": "PWA update v1 to v2",
                    "publication": "composition",
                    "document": "pwa-update-v2-migration",
                    "destination": "capabilities/pwa/migrations/update-v1-to-v2.md",
                },
            ],
        )

        text = CAPABILITIES.read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        self.assertIn("[Choose Website or Web application](../web/)", text)
        self.assertIn("[Website](../website/)", text)
        self.assertIn("[Web application](../webapp/)", text)
        self.assertIn("[Progressive Web App capability](pwa/)", text)
        self.assertIn("defines public navigation only", normalized)
        self.assertIn(
            "Canonical artifact, foundation, capability, runtime, routing, viewport, and evidence semantics remain owned by the `composition` provider",
            normalized,
        )
        self.assertIn("provider-owned [Choose Website or Web application]", normalized)
        self.assertIn("The Site does not restate those decision rules here", normalized)
        self.assertIn("[Policy PWA usage guide](../policy/pwa/)", text)
        self.assertIn("it is not the Composition capability document", normalized)
        self.assertNotIn("network-first", text)
        self.assertNotIn("cache-first", text)
        self.assertNotIn("Service Worker is required", text)

    def test_japanese_projection_points_to_same_reader_destinations(self) -> None:
        text = JAPANESE_CAPABILITIES.read_text(encoding="utf-8")
        normalized = " ".join(text.split())

        self.assertIn("[Website と Web application の選び方](/web/)", text)
        self.assertIn("[Website](/website/)", text)
        self.assertIn("[Web application](/webapp/)", text)
        self.assertIn("[Progressive Web App capability](/capabilities/pwa/)", text)
        self.assertIn("このページが定義するのは public navigation だけです", normalized)
        self.assertIn(
            "artifact、foundation、capability、runtime、routing、viewport、evidence の canonical semantics は `composition` provider が所有します",
            normalized,
        )
        self.assertIn("Site はその decision rule をここで再定義しません", normalized)
        self.assertIn("[Policy PWA usage guide](/policy/pwa/)", text)
        self.assertIn("Composition capability document ではありません", normalized)


if __name__ == "__main__":
    unittest.main()
