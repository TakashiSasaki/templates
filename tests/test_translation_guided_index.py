from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "translations" / "manifest.json"
CANONICAL = ROOT / "docs" / "index.md"
TRANSLATION = ROOT / "translations" / "ja" / "docs" / "index.md"
LINK_TARGET = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+", re.MULTILINE)


class GuidedIndexTranslationTests(unittest.TestCase):
    def test_documentation_index_is_reader_and_guided_overlay(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entry = next(
            item
            for item in manifest["translations"]
            if item["canonical"] == "docs/index.md" and item["language"] == "ja"
        )

        self.assertEqual(entry["translation"], "translations/ja/docs/index.md")
        self.assertEqual(
            entry["canonical_blob_sha"],
            "cc8b52814df780c2bb0f6b5920c1898ef9d2bf21",
        )
        self.assertEqual(entry["surfaces"], ["reader", "guided"])

    def test_guided_translation_preserves_canonical_structure_and_targets(self) -> None:
        canonical = CANONICAL.read_text(encoding="utf-8")
        translation = TRANSLATION.read_text(encoding="utf-8")

        self.assertEqual(
            [len(match.group(1)) for match in HEADING.finditer(translation)],
            [len(match.group(1)) for match in HEADING.finditer(canonical)],
        )
        self.assertEqual(
            LINK_TARGET.findall(translation),
            LINK_TARGET.findall(canonical),
        )


if __name__ == "__main__":
    unittest.main()
