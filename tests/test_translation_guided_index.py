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
GUIDED_LINK = re.compile(r"^- \[[^\]]+\]\(.+\)[ \t]+[-–—][ \t]+\S.+$")
JA_NOTICE = "> **参考訳（非正本）:**"


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
            "0a78525a3b4a9198187eb5e5f8e05825921e8be0",
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

    def test_guided_translation_lines_use_overlay_shape(self) -> None:
        for number, raw_line in enumerate(
            TRANSLATION.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            line = raw_line.strip()
            if not line:
                continue
            with self.subTest(line=number):
                self.assertTrue(
                    line.startswith("#")
                    or line.startswith(JA_NOTICE)
                    or bool(GUIDED_LINK.fullmatch(line)),
                    f"invalid guided translation content at "
                    f"translations/ja/docs/index.md:{number}: {raw_line!r}",
                )


if __name__ == "__main__":
    unittest.main()
