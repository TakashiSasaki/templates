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


def write_manifest_payload(root: Path, payload: dict[str, object]) -> None:
    (root / "translations" / "manifest.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def write_manifest_entries(root: Path, entries: list[dict[str, object]]) -> None:
    write_manifest_payload(
        root,
        {
            "schema_version": 2,
            "canonical_language": "en",
            "translations": entries,
        },
    )


def write_manifest(root: Path, entry: dict[str, object]) -> None:
    write_manifest_entries(root, [entry])


def prepare_guided_translation(
    root: Path,
    *,
    canonical_path: str = "docs/index.md",
    translation_path: str = "translations/ja/docs/index.md",
    translation_text: str = "# ナビゲーション\n\n> **参考訳（非正本）:** test\n",
) -> bytes:
    canonical = b"# Navigation\n"
    canonical_file = root / canonical_path
    translation_file = root / translation_path
    canonical_file.parent.mkdir(parents=True, exist_ok=True)
    translation_file.parent.mkdir(parents=True, exist_ok=True)
    canonical_file.write_bytes(canonical)
    translation_file.write_text(translation_text, encoding="utf-8")
    (root / "docs").mkdir(exist_ok=True)
    write_catalog(root)
    return canonical


def guided_entry(canonical: bytes) -> dict[str, object]:
    return {
        "canonical": "docs/index.md",
        "language": "ja",
        "translation": "translations/ja/docs/index.md",
        "canonical_blob_sha": blob_sha(canonical),
        "surfaces": ["guided"],
    }


class TranslationContractTests(unittest.TestCase):
    def test_repository_manifest_is_valid(self) -> None:
        result = validate(ROOT)
        self.assertIn("translations validated: 3", result)
        self.assertIn("reader translations: 0", result)
        self.assertIn("guided translations: 3", result)

    def test_guided_index_outside_reader_catalog_is_valid(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
            root = Path(directory)
            canonical = prepare_guided_translation(root)
            write_manifest(root, guided_entry(canonical))
            self.assertIn("guided translations: 1", validate(root))

    def test_reader_surface_still_requires_catalog_membership(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
            root = Path(directory)
            canonical = prepare_guided_translation(root)
            entry = guided_entry(canonical)
            entry["surfaces"] = ["reader"]
            write_manifest(root, entry)
            with self.assertRaisesRegex(TranslationError, "not a published canonical document"):
                validate(root)

    def test_canonical_change_invalidates_translation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
            root = Path(directory)
            original = prepare_guided_translation(root)
            (root / "docs" / "index.md").write_bytes(b"# Changed\n")
            write_manifest(root, guided_entry(original))
            with self.assertRaisesRegex(TranslationError, "stale translation"):
                validate(root)

    def test_guided_surface_requires_index_filename(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
            root = Path(directory)
            canonical = prepare_guided_translation(
                root,
                canonical_path="docs/architecture.md",
                translation_path="translations/ja/docs/architecture.md",
                translation_text="# アーキテクチャ\n\n> **参考訳（非正本）:** test\n",
            )
            write_manifest(
                root,
                {
                    "canonical": "docs/architecture.md",
                    "language": "ja",
                    "translation": "translations/ja/docs/architecture.md",
                    "canonical_blob_sha": blob_sha(canonical),
                    "surfaces": ["guided"],
                },
            )
            with self.assertRaisesRegex(
                TranslationError,
                "must be an index.md document for guided use",
            ):
                validate(root)

    def test_japanese_translation_notice_is_required(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
            root = Path(directory)
            canonical = prepare_guided_translation(
                root,
                translation_text="# ナビゲーション\n",
            )
            write_manifest(root, guided_entry(canonical))
            with self.assertRaisesRegex(
                TranslationError,
                "must place the non-authoritative notice immediately after",
            ):
                validate(root)

    def test_duplicate_canonical_language_pair_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
            root = Path(directory)
            canonical = prepare_guided_translation(root)
            entry = guided_entry(canonical)
            write_manifest_entries(root, [entry, dict(entry)])
            with self.assertRaisesRegex(
                TranslationError,
                "duplicate canonical/language translation pair",
            ):
                validate(root)

    def test_translation_path_must_mirror_canonical_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
            root = Path(directory)
            canonical = prepare_guided_translation(root)
            entry = guided_entry(canonical)
            entry["translation"] = "translations/ja/other/index.md"
            write_manifest(root, entry)
            with self.assertRaisesRegex(
                TranslationError,
                "must mirror the canonical path",
            ):
                validate(root)

    def test_undeclared_language_translation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
            root = Path(directory)
            canonical = prepare_guided_translation(root)
            extra = root / "translations" / "ja" / "docs" / "extra.md"
            extra.write_text(
                "# 追加\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            write_manifest(root, guided_entry(canonical))
            with self.assertRaisesRegex(TranslationError, "undeclared translation Markdown"):
                validate(root)

    def test_root_level_translation_markdown_is_not_silently_ignored(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
            root = Path(directory)
            canonical = prepare_guided_translation(root)
            (root / "translations" / "NOTES.md").write_text(
                "# Maintainer note\n",
                encoding="utf-8",
            )
            write_manifest(root, guided_entry(canonical))
            with self.assertRaisesRegex(
                TranslationError,
                "undeclared translation Markdown: translations/NOTES.md",
            ):
                validate(root)

    def test_invalid_schema_version_is_rejected(self) -> None:
        for version in (1, 3, "2"):
            with self.subTest(version=version):
                with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
                    root = Path(directory)
                    canonical = prepare_guided_translation(root)
                    write_manifest_payload(
                        root,
                        {
                            "schema_version": version,
                            "canonical_language": "en",
                            "translations": [guided_entry(canonical)],
                        },
                    )
                    with self.assertRaisesRegex(
                        TranslationError,
                        "schema_version must be integer 2",
                    ):
                        validate(root)

    def test_unsafe_path_traversal_in_manifest_is_rejected(self) -> None:
        unsafe_paths = ("../docs/index.md", "/etc/passwd", ".git/config")
        for unsafe in unsafe_paths:
            with self.subTest(unsafe=unsafe):
                with tempfile.TemporaryDirectory(prefix="skill-translation-") as directory:
                    root = Path(directory)
                    canonical = prepare_guided_translation(root)
                    entry = guided_entry(canonical)
                    entry["canonical"] = unsafe
                    write_manifest(root, entry)
                    with self.assertRaisesRegex(
                        TranslationError,
                        "must be a safe relative POSIX path",
                    ):
                        validate(root)


if __name__ == "__main__":
    unittest.main()
