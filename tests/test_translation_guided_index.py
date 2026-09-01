from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "translations" / "manifest.json"
CANONICAL = ROOT / "docs" / "index.md"
TRANSLATION = ROOT / "translations" / "ja" / "docs" / "index.md"
TRANSLATION_ROOT = ROOT / "translations" / "ja"
LINK_TARGET = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+", re.MULTILINE)
GUIDED_LINK = re.compile(r"^- \[[^\]]+\]\(.+\)[ \t]+[-–—][ \t]+\S.+$")
JA_NOTICE = "> **参考訳（非正本）:**"


def canonical_target_identity(source: Path, target: str, *, translated: bool) -> str:
    resolved = (source.parent / target).resolve()
    if translated:
        try:
            return resolved.relative_to(TRANSLATION_ROOT).as_posix()
        except ValueError:
            pass
    return resolved.relative_to(ROOT).as_posix()


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
            "2ccf418f0639ff3029de19bdd0faf7198d78eb71",
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
            [
                canonical_target_identity(TRANSLATION, target, translated=True)
                for target in LINK_TARGET.findall(translation)
            ],
            [
                canonical_target_identity(CANONICAL, target, translated=False)
                for target in LINK_TARGET.findall(canonical)
            ],
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
