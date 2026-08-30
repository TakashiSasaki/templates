from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _pages(nodes):
    for node in nodes:
        if "publication" in node:
            yield node
        yield from _pages(node.get("children", []))


class ComposerArchitecturePublicationCutoverTests(unittest.TestCase):
    def test_composer_architecture_keeps_stable_publication_identity(self) -> None:
        manifest = json.loads(
            (ROOT / "site-manifest.json").read_text(encoding="utf-8")
        )
        matches = [
            page
            for page in _pages(manifest["navigation"])
            if page.get("publication") == "composition"
            and page.get("document") == "composer-mvp"
        ]

        self.assertEqual(
            matches,
            [
                {
                    "title": "Composer architecture",
                    "publication": "composition",
                    "document": "composer-mvp",
                    "destination": "composition/architecture/composer-mvp.md",
                }
            ],
        )

    def test_composer_architecture_reader_locale_uses_new_label(self) -> None:
        locales = json.loads(
            (ROOT / "reader-navigation-locales.json").read_text(encoding="utf-8")
        )
        japanese = next(
            locale for locale in locales["locales"] if locale["language"] == "ja"
        )
        matches = [
            label for label in japanese["labels"] if label["id"] == "composer-mvp"
        ]

        self.assertEqual(
            matches,
            [
                {
                    "id": "composer-mvp",
                    "canonical": "Composer architecture",
                    "localized": "Composer architecture",
                }
            ],
        )

    def test_composer_mvp_is_not_reader_facing_site_terminology(self) -> None:
        for path in ("site-manifest.json", "reader-navigation-locales.json"):
            self.assertNotIn(
                "Composer MVP", (ROOT / path).read_text(encoding="utf-8")
            )


if __name__ == "__main__":
    unittest.main()
