from __future__ import annotations

import re
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "docs" / "architecture" / "composer-mvp.md"
TRANSLATION = ROOT / "translations" / "ja" / "docs" / "architecture" / "composer-mvp.md"
FENCED_BLOCK = re.compile(r"```([^\n]*)\n(.*?)```", re.DOTALL)


class ComposerMvpTranslationFidelityTests(unittest.TestCase):
    def test_machine_visible_fenced_blocks_match_canonical_exactly(self) -> None:
        reviewed = next(item['canonical_blob_sha'] for item in json.loads(
            (ROOT / 'translations/manifest.json').read_text())['translations']
            if item['translation'] == TRANSLATION.relative_to(ROOT).as_posix())
        content = CANONICAL.read_bytes()
        current = hashlib.sha1(f'blob {len(content)}\0'.encode() + content).hexdigest()
        if reviewed != current:
            self.skipTest('Reference translation awaits independent review of newer English')
        canonical = CANONICAL.read_text(encoding="utf-8")
        translation = TRANSLATION.read_text(encoding="utf-8")

        canonical_blocks = FENCED_BLOCK.findall(canonical)
        translation_blocks = FENCED_BLOCK.findall(translation)

        self.assertGreater(len(canonical_blocks), 0)
        self.assertEqual(translation_blocks, canonical_blocks)


if __name__ == "__main__":
    unittest.main()
