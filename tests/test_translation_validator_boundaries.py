from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_publication_catalog import CatalogError, safe_relative_path
from scripts.validate_translations import TranslationError, validate


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()  # noqa: S324


def prepare_root(
    root: Path,
    *,
    language: str = "ja",
    canonical: str = "docs/index.md",
    translation: str | None = None,
    translation_text: str = "# ナビゲーション\n\n> **参考訳（非正本）:** test\n",
    publication_schema_version: object = 3,
) -> tuple[bytes, dict[str, object]]:
    if translation is None:
        translation = f"translations/{language}/{canonical}"
    canonical_bytes = b"# Navigation\n"
    canonical_path = root / canonical
    translation_path = root / translation
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    translation_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_bytes(canonical_bytes)
    translation_path.write_text(translation_text, encoding="utf-8")
    (root / "docs" / "publication-catalog.json").write_text(
        json.dumps(
            {
                "schema_version": publication_schema_version,
                "documents": [],
                "assets": [],
            }
        ),
        encoding="utf-8",
    )
    entry: dict[str, object] = {
        "canonical": canonical,
        "language": language,
        "translation": translation,
        "canonical_blob_sha": blob_sha(canonical_bytes),
        "surfaces": ["guided"],
    }
    return canonical_bytes, entry


def write_manifest(root: Path, entries: list[dict[str, object]], **overrides: object) -> None:
    payload: dict[str, object] = {
        "schema_version": 2,
        "canonical_language": "en",
        "translations": entries,
    }
    payload.update(overrides)
    (root / "translations" / "manifest.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


class TranslationValidatorBoundaryTests(unittest.TestCase):
    def test_manifest_schema_version_is_strictly_v2(self) -> None:
        for version in (1, 3, "2", True):
            with self.subTest(version=version):
                with tempfile.TemporaryDirectory(prefix="webapp-translation-") as directory:
                    root = Path(directory)
                    _, entry = prepare_root(root)
                    write_manifest(root, [entry], schema_version=version)
                    with self.assertRaisesRegex(
                        TranslationError, "schema_version must be integer 2"
                    ):
                        validate(root)

    def test_publication_catalog_schema_version_is_strictly_v3(self) -> None:
        for version in (1, 2, 4, "3", 3.0, True, None, [3]):
            with self.subTest(version=version):
                with tempfile.TemporaryDirectory(prefix="webapp-translation-") as directory:
                    root = Path(directory)
                    _, entry = prepare_root(
                        root,
                        publication_schema_version=version,
                    )
                    write_manifest(root, [entry])
                    with self.assertRaisesRegex(
                        TranslationError,
                        "publication catalog schema_version must be integer 3",
                    ):
                        validate(root)

    def test_canonical_language_must_be_english(self) -> None:
        with tempfile.TemporaryDirectory(prefix="webapp-translation-") as directory:
            root = Path(directory)
            _, entry = prepare_root(root)
            write_manifest(root, [entry], canonical_language="fr")
            with self.assertRaisesRegex(
                TranslationError, "canonical_language must be en"
            ):
                validate(root)

    def test_canonical_blob_sha_must_be_full_lowercase_git_sha(self) -> None:
        for invalid in ("abc", "A" * 40, "g" * 40):
            with self.subTest(invalid=invalid):
                with tempfile.TemporaryDirectory(prefix="webapp-translation-") as directory:
                    root = Path(directory)
                    _, entry = prepare_root(root)
                    entry["canonical_blob_sha"] = invalid
                    write_manifest(root, [entry])
                    with self.assertRaisesRegex(
                        TranslationError, "full lowercase Git blob SHA"
                    ):
                        validate(root)

    def test_surface_list_rejects_empty_unknown_and_duplicate_values(self) -> None:
        for surfaces in ([], ["search"], ["guided", "guided"]):
            with self.subTest(surfaces=surfaces):
                with tempfile.TemporaryDirectory(prefix="webapp-translation-") as directory:
                    root = Path(directory)
                    _, entry = prepare_root(root)
                    entry["surfaces"] = surfaces
                    write_manifest(root, [entry])
                    with self.assertRaises(TranslationError):
                        validate(root)

    def test_translation_entries_must_use_markdown_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="webapp-translation-") as directory:
            root = Path(directory)
            _, entry = prepare_root(
                root,
                canonical="docs/index.txt",
                translation="translations/ja/docs/index.txt",
            )
            write_manifest(root, [entry])
            with self.assertRaisesRegex(
                TranslationError, "canonical and translation paths must be Markdown"
            ):
                validate(root)

    def test_null_byte_path_is_rejected_as_translation_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="webapp-translation-") as directory:
            root = Path(directory)
            _, entry = prepare_root(root)
            entry["canonical"] = "docs/\0index.md"
            write_manifest(root, [entry])
            with self.assertRaisesRegex(
                TranslationError, "safe relative POSIX path"
            ):
                validate(root)

    def test_japanese_language_subtag_requires_japanese_notice(self) -> None:
        with tempfile.TemporaryDirectory(prefix="webapp-translation-") as directory:
            root = Path(directory)
            _, entry = prepare_root(
                root,
                language="ja-jp",
                translation_text="# ナビゲーション\n\n> translated notice\n",
            )
            write_manifest(root, [entry])
            with self.assertRaisesRegex(
                TranslationError, "standard Japanese non-authoritative notice|non-authoritative notice"
            ):
                validate(root)

    def test_undeclared_non_markdown_translation_content_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="webapp-translation-") as directory:
            root = Path(directory)
            _, entry = prepare_root(root)
            extra = root / "translations" / "ja" / "notes.txt"
            extra.write_text("not declared", encoding="utf-8")
            write_manifest(root, [entry])
            with self.assertRaisesRegex(
                TranslationError, "translation content must be declared Markdown"
            ):
                validate(root)

    def test_publication_catalog_path_rejects_null_byte_before_filesystem_use(self) -> None:
        with self.assertRaisesRegex(CatalogError, "safe non-empty relative POSIX path"):
            safe_relative_path("docs/\0overview.md", "documents[0].source")


if __name__ == "__main__":
    unittest.main()
