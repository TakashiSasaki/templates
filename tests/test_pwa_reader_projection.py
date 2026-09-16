from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES = ROOT / "docs" / "capabilities.md"
JAPANESE_CAPABILITIES = ROOT / "translations" / "ja" / "docs" / "capabilities.md"
SITE_MANIFEST = ROOT / "site-manifest.json"


def iter_pages(nodes: list[dict[str, Any]] | dict[str, Any]):
    if isinstance(nodes, dict):
        for child in nodes.values():
            if isinstance(child, list):
                yield from iter_pages(child)
        return
    for node in nodes:
        if "children" in node:
            yield from iter_pages(node["children"])
        else:
            yield node


class PwaReaderProjectionTests(unittest.TestCase):

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
