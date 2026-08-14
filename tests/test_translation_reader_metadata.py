from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.translation_reader_metadata import (
    TranslationReaderMetadataError,
    exclude_translation_from_search,
)


class TranslationReaderMetadataTests(unittest.TestCase):
    def test_adds_front_matter_when_translation_has_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "translation.md"
            path.write_text(
                "# Translation\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )

            exclude_translation_from_search(path)

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "---\nsearch:\n  exclude: true\n---\n\n"
                "# Translation\n\n> **参考訳（非正本）:** test\n",
            )

    def test_preserves_existing_front_matter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "translation.md"
            path.write_text(
                "---\ndescription: translated\n---\n\n"
                "# Translation\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )

            exclude_translation_from_search(path)

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "---\ndescription: translated\nsearch:\n  exclude: true\n---\n\n"
                "# Translation\n\n> **参考訳（非正本）:** test\n",
            )

    def test_existing_search_metadata_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "translation.md"
            path.write_text(
                "---\nsearch:\n  exclude: false\n---\n\n# Translation\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                TranslationReaderMetadataError,
                "already defines top-level search metadata",
            ):
                exclude_translation_from_search(path)


if __name__ == "__main__":
    unittest.main()
