from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_translations import TranslationError, validate

ROOT = Path(__file__).resolve().parents[1]


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


class TranslationContractTests(unittest.TestCase):
    def test_repository_translation_manifest_is_valid(self) -> None:
        result = validate(ROOT)
        self.assertIn("canonical language: en", result)
        self.assertIn("translations validated: 10", result)

    def test_canonical_change_makes_translation_stale(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "translations" / "ja" / "docs").mkdir(parents=True)

            original = b"# Canonical\n\nOriginal English.\n"
            current = b"# Canonical\n\nChanged English.\n"
            (root / "docs" / "overview.md").write_bytes(current)
            (root / "translations" / "ja" / "docs" / "overview.md").write_text(
                "> **参考訳（非正本）:** test\n\n# Translation\n",
                encoding="utf-8",
            )
            (root / "docs" / "publication-catalog.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "documents": [
                            {
                                "id": "overview",
                                "source": "docs/overview.md",
                                "optional": False,
                                "home": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "translations" / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "canonical_language": "en",
                        "translations": [
                            {
                                "canonical": "docs/overview.md",
                                "language": "ja",
                                "translation": "translations/ja/docs/overview.md",
                                "canonical_blob_sha": blob_sha(original),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(TranslationError, "stale translation"):
                validate(root)

    def test_translation_path_must_mirror_canonical_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "translations" / "ja").mkdir(parents=True)
            canonical = b"# Canonical\n"
            (root / "docs" / "overview.md").write_bytes(canonical)
            (root / "translations" / "ja" / "overview.md").write_text(
                "> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            (root / "docs" / "publication-catalog.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "documents": [
                            {
                                "id": "overview",
                                "source": "docs/overview.md",
                                "optional": False,
                                "home": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "translations" / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "canonical_language": "en",
                        "translations": [
                            {
                                "canonical": "docs/overview.md",
                                "language": "ja",
                                "translation": "translations/ja/overview.md",
                                "canonical_blob_sha": blob_sha(canonical),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(TranslationError, "must mirror the canonical path"):
                validate(root)


if __name__ == "__main__":
    unittest.main()
