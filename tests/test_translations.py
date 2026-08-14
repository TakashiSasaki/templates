from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.validate_translations import TranslationError, validate

ROOT = Path(__file__).resolve().parents[1]


def blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object identity


def write_catalog(root: Path, *, source: str = "docs/overview.md") -> None:
    (root / "docs" / "publication-catalog.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "documents": [
                    {
                        "id": "overview",
                        "source": source,
                        "optional": False,
                        "home": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def translation_entry(
    *,
    canonical_blob_sha: str,
    canonical: str = "docs/overview.md",
    translation: str = "translations/ja/docs/overview.md",
    surfaces: list[str] | None = None,
) -> dict[str, object]:
    return {
        "canonical": canonical,
        "language": "ja",
        "translation": translation,
        "canonical_blob_sha": canonical_blob_sha,
        "surfaces": surfaces if surfaces is not None else ["reader"],
    }


def write_manifest(root: Path, entries: list[dict[str, object]]) -> None:
    (root / "translations" / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "canonical_language": "en",
                "translations": entries,
            }
        ),
        encoding="utf-8",
    )


def prepare_single_translation(root: Path) -> bytes:
    (root / "docs").mkdir()
    (root / "translations" / "ja" / "docs").mkdir(parents=True)
    canonical = b"# Canonical\n"
    (root / "docs" / "overview.md").write_bytes(canonical)
    (root / "translations" / "ja" / "docs" / "overview.md").write_text(
        "# Translation\n\n> **参考訳（非正本）:** test\n",
        encoding="utf-8",
    )
    write_catalog(root)
    return canonical


class TranslationContractTests(unittest.TestCase):
    def test_repository_translation_manifest_is_valid(self) -> None:
        result = validate(ROOT)
        self.assertIn("canonical language: en", result)
        self.assertIn("translations validated: 15", result)
        self.assertIn("reader translations: 14", result)
        self.assertIn("guided translations: 5", result)

    def test_guided_index_may_be_outside_reader_catalog(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "translations" / "ja" / "docs").mkdir(parents=True)
            canonical = b"# Navigation\n"
            (root / "docs" / "index.md").write_bytes(canonical)
            (root / "docs" / "overview.md").write_text("# Overview\n", encoding="utf-8")
            (root / "translations" / "ja" / "docs" / "index.md").write_text(
                "# ナビゲーション\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            write_catalog(root)
            write_manifest(
                root,
                [
                    translation_entry(
                        canonical_blob_sha=blob_sha(canonical),
                        canonical="docs/index.md",
                        translation="translations/ja/docs/index.md",
                        surfaces=["guided"],
                    )
                ],
            )

            result = validate(root)
            self.assertIn("reader translations: 0", result)
            self.assertIn("guided translations: 1", result)

    def test_reader_surface_requires_publication_catalog_membership(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "translations" / "ja" / "docs").mkdir(parents=True)
            canonical = b"# Navigation\n"
            (root / "docs" / "index.md").write_bytes(canonical)
            (root / "docs" / "overview.md").write_text("# Overview\n", encoding="utf-8")
            (root / "translations" / "ja" / "docs" / "index.md").write_text(
                "# ナビゲーション\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            write_catalog(root)
            write_manifest(
                root,
                [
                    translation_entry(
                        canonical_blob_sha=blob_sha(canonical),
                        canonical="docs/index.md",
                        translation="translations/ja/docs/index.md",
                        surfaces=["reader"],
                    )
                ],
            )

            with self.assertRaisesRegex(
                TranslationError,
                "is not a published canonical document",
            ):
                validate(root)

    def test_guided_surface_requires_index_document(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            canonical = prepare_single_translation(root)
            write_manifest(
                root,
                [
                    translation_entry(
                        canonical_blob_sha=blob_sha(canonical),
                        surfaces=["guided"],
                    )
                ],
            )

            with self.assertRaisesRegex(TranslationError, "must be an index.md document"):
                validate(root)

    def test_unknown_and_duplicate_surfaces_are_rejected(self) -> None:
        for surfaces, message in [
            (["reader", "search"], "must be one of reader or guided"),
            (["reader", "reader"], "must not contain duplicate surfaces"),
            ([], "must be a non-empty array"),
        ]:
            with self.subTest(surfaces=surfaces):
                with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
                    root = Path(directory)
                    canonical = prepare_single_translation(root)
                    write_manifest(
                        root,
                        [
                            translation_entry(
                                canonical_blob_sha=blob_sha(canonical),
                                surfaces=surfaces,
                            )
                        ],
                    )
                    with self.assertRaisesRegex(TranslationError, message):
                        validate(root)

    def test_canonical_change_makes_translation_stale(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "translations" / "ja" / "docs").mkdir(parents=True)
            original = b"# Canonical\n\nOriginal English.\n"
            current = b"# Canonical\n\nChanged English.\n"
            (root / "docs" / "overview.md").write_bytes(current)
            (root / "translations" / "ja" / "docs" / "overview.md").write_text(
                "# Translation\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            write_catalog(root)
            write_manifest(root, [translation_entry(canonical_blob_sha=blob_sha(original))])
            with self.assertRaisesRegex(TranslationError, "stale translation"):
                validate(root)

    def test_translation_path_must_mirror_canonical_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            canonical = prepare_single_translation(root)
            wrong_path = root / "translations" / "ja" / "overview.md"
            wrong_path.write_text(
                "# Translation\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            write_manifest(
                root,
                [
                    translation_entry(
                        canonical_blob_sha=blob_sha(canonical),
                        translation="translations/ja/overview.md",
                    )
                ],
            )
            with self.assertRaisesRegex(TranslationError, "must mirror the canonical path"):
                validate(root)

    def test_japanese_translation_missing_notice_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            canonical = prepare_single_translation(root)
            translation = root / "translations" / "ja" / "docs" / "overview.md"
            translation.write_text("# Translation\n", encoding="utf-8")
            write_manifest(root, [translation_entry(canonical_blob_sha=blob_sha(canonical))])
            with self.assertRaisesRegex(
                TranslationError,
                "must place the non-authoritative notice immediately after",
            ):
                validate(root)

    def test_japanese_translation_notice_before_title_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            canonical = prepare_single_translation(root)
            translation = root / "translations" / "ja" / "docs" / "overview.md"
            translation.write_text(
                "> **参考訳（非正本）:** test\n\n# Translation\n",
                encoding="utf-8",
            )
            write_manifest(root, [translation_entry(canonical_blob_sha=blob_sha(canonical))])
            with self.assertRaisesRegex(TranslationError, "must place a top-level title before"):
                validate(root)

    def test_japanese_translation_front_matter_before_title_allowed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            canonical = prepare_single_translation(root)
            translation = root / "translations" / "ja" / "docs" / "overview.md"
            translation.write_text(
                "---\ndescription: translated\n---\n\n"
                "# Translation\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            write_manifest(root, [translation_entry(canonical_blob_sha=blob_sha(canonical))])
            self.assertIn("translations validated: 1", validate(root))

    @unittest.skipIf(os.name == "nt", "symlink creation is not reliably available on Windows")
    def test_symlink_translation_path_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            canonical = prepare_single_translation(root)
            translation = root / "translations" / "ja" / "docs" / "overview.md"
            target = root / "translations" / "ja" / "docs" / "target.md"
            translation.unlink()
            target.write_text(
                "# Translation\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            translation.symlink_to(target.name)
            write_manifest(root, [translation_entry(canonical_blob_sha=blob_sha(canonical))])
            with self.assertRaisesRegex(TranslationError, "must not traverse a symlink"):
                validate(root)

    def test_undeclared_translation_file_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            canonical = prepare_single_translation(root)
            undeclared = root / "translations" / "ja" / "docs" / "extra.md"
            undeclared.write_text(
                "# Extra\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            write_manifest(root, [translation_entry(canonical_blob_sha=blob_sha(canonical))])
            with self.assertRaisesRegex(TranslationError, "undeclared translation Markdown"):
                validate(root)

    def test_duplicate_translation_pair_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="translation-test-") as directory:
            root = Path(directory)
            canonical = prepare_single_translation(root)
            entry = translation_entry(canonical_blob_sha=blob_sha(canonical))
            write_manifest(root, [entry, dict(entry)])
            with self.assertRaisesRegex(
                TranslationError,
                "duplicate canonical/language translation pair",
            ):
                validate(root)


if __name__ == "__main__":
    unittest.main()
