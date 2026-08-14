#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from validate_translations import TranslationError, validate

ROOT = Path(__file__).resolve().parents[2]


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()  # noqa: S324


def write_catalog(root: Path) -> None:
    (root / "docs" / "publication-catalog.json").write_text(
        json.dumps({"schema_version": 1, "documents": []}), encoding="utf-8"
    )


def write_manifest(root: Path, entry: dict[str, object]) -> None:
    (root / "translations" / "manifest.json").write_text(
        json.dumps({"schema_version": 2, "canonical_language": "en", "translations": [entry]}),
        encoding="utf-8",
    )


class TranslationContractTests(unittest.TestCase):
    def test_repository_manifest_is_valid(self) -> None:
        result = validate(ROOT)
        self.assertIn("translations validated: 3", result)
        self.assertIn("reader translations: 0", result)
        self.assertIn("guided translations: 3", result)

    def test_guided_index_outside_reader_catalog_is_valid(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "translations" / "ja" / "docs").mkdir(parents=True)
            canonical = b"# Navigation\n"
            (root / "docs" / "index.md").write_bytes(canonical)
            (root / "translations" / "ja" / "docs" / "index.md").write_text(
                "# ナビゲーション\n\n> **参考訳（非正本）:** test\n", encoding="utf-8"
            )
            write_catalog(root)
            write_manifest(
                root,
                {
                    "canonical": "docs/index.md",
                    "language": "ja",
                    "translation": "translations/ja/docs/index.md",
                    "canonical_blob_sha": blob_sha(canonical),
                    "surfaces": ["guided"],
                },
            )
            self.assertIn("guided translations: 1", validate(root))

    def test_reader_surface_still_requires_catalog_membership(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "translations" / "ja" / "docs").mkdir(parents=True)
            canonical = b"# Navigation\n"
            (root / "docs" / "index.md").write_bytes(canonical)
            (root / "translations" / "ja" / "docs" / "index.md").write_text(
                "# ナビゲーション\n\n> **参考訳（非正本）:** test\n", encoding="utf-8"
            )
            write_catalog(root)
            write_manifest(
                root,
                {
                    "canonical": "docs/index.md",
                    "language": "ja",
                    "translation": "translations/ja/docs/index.md",
                    "canonical_blob_sha": blob_sha(canonical),
                    "surfaces": ["reader"],
                },
            )
            with self.assertRaisesRegex(TranslationError, "not a published canonical document"):
                validate(root)

    def test_canonical_change_invalidates_translation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "translations" / "ja" / "docs").mkdir(parents=True)
            original = b"# Navigation\n"
            (root / "docs" / "index.md").write_bytes(b"# Changed\n")
            (root / "translations" / "ja" / "docs" / "index.md").write_text(
                "# ナビゲーション\n\n> **参考訳（非正本）:** test\n", encoding="utf-8"
            )
            write_catalog(root)
            write_manifest(
                root,
                {
                    "canonical": "docs/index.md",
                    "language": "ja",
                    "translation": "translations/ja/docs/index.md",
                    "canonical_blob_sha": blob_sha(original),
                    "surfaces": ["guided"],
                },
            )
            with self.assertRaisesRegex(TranslationError, "stale translation"):
                validate(root)


if __name__ == "__main__":
    unittest.main()
