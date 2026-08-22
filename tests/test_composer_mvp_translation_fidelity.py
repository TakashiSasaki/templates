from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "docs" / "architecture" / "composer-mvp.md"
TRANSLATION = ROOT / "translations" / "ja" / "docs" / "architecture" / "composer-mvp.md"
FENCED_BLOCK = re.compile(r"```([^\n]*)\n(.*?)```", re.DOTALL)


class ComposerMvpTranslationFidelityTests(unittest.TestCase):
    def test_machine_visible_fenced_blocks_match_canonical_exactly(self) -> None:
        canonical = CANONICAL.read_text(encoding="utf-8")
        translation = TRANSLATION.read_text(encoding="utf-8")

        canonical_blocks = FENCED_BLOCK.findall(canonical)
        translation_blocks = FENCED_BLOCK.findall(translation)

        self.assertGreater(len(canonical_blocks), 0)
        self.assertEqual(translation_blocks, canonical_blocks)


if __name__ == "__main__":
    unittest.main()
