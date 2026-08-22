from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_translations import TranslationError, validate

ROOT = Path(__file__).resolve().parents[1]


def blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object identity


def write_catalog(root: Path, source: str = "README.md") -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "publication-catalog.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
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


def write_manifest(
    root: Path,
    *,
    sha: str,
    canonical: str = "README.md",
    translation: str = "translations/ja/README.md",
    surfaces: list[str] | None = None,
) -> None:
    (root / "translations").mkdir(parents=True, exist_ok=True)
    (root / "translations" / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "canonical_language": "en",
                "translations": [
                    {
                        "canonical": canonical,
                        "language": "ja",
                        "translation": translation,
                        "canonical_blob_sha": sha,
                        "surfaces": surfaces if surfaces is not None else ["reader"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def prepare_translation(root: Path) -> bytes:
    canonical = b"# Composition\n\nCanonical.\n"
    (root / "README.md").write_bytes(canonical)
    (root / "translations" / "ja").mkdir(parents=True)
    (root / "translations" / "ja" / "README.md").write_text(
        "# Composition\n\n> **参考訳（非正本）:** test\n\nTranslation.\n",
        encoding="utf-8",
    )
    write_catalog(root)
    return canonical


class TranslationContractTests(unittest.TestCase):
    def test_repository_translation_manifest_is_valid(self) -> None:
        manifest = json.loads(
            (ROOT / "translations" / "manifest.json").read_text(encoding="utf-8")
        )
        translations = manifest["translations"]
        reader_count = sum(
            "reader" in entry["surfaces"] for entry in translations
        )
        guided_count = sum(
            "guided" in entry["surfaces"] for entry in translations
        )

        result = validate(ROOT)
        self.assertIn("canonical language: en", result)
        self.assertIn(f"translations validated: {len(translations)}", result)
        self.assertIn(f"reader translations: {reader_count}", result)
        self.assertIn(f"guided translations: {guided_count}", result)

    def test_repository_reader_translations_include_authority_guides(self) -> None:
        manifest = json.loads(
            (ROOT / "translations" / "manifest.json").read_text(encoding="utf-8")
        )
        reader_canonicals = {
            entry["canonical"]
            for entry in manifest["translations"]
            if "reader" in entry["surfaces"]
        }
        self.assertTrue(
            {
                "README.md",
                "catalog/README.md",
                "docs/publication-catalog.md",
                "schemas/README.md",
            }.issubset(reader_canonicals)
        )

    def test_canonical_change_makes_translation_stale(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-translation-") as directory:
            root = Path(directory)
            canonical = prepare_translation(root)
            write_manifest(root, sha=blob_sha(canonical))
            (root / "README.md").write_text(
                "# Composition\n\nChanged.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(TranslationError, "stale translation"):
                validate(root)

    def test_reader_surface_requires_published_canonical(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-translation-") as directory:
            root = Path(directory)
            canonical = prepare_translation(root)
            (root / "docs" / "other.md").write_bytes(canonical)
            (root / "translations" / "ja" / "docs").mkdir(parents=True)
            (root / "translations" / "ja" / "docs" / "other.md").write_text(
                "# Other\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            write_manifest(
                root,
                sha=blob_sha(canonical),
                canonical="docs/other.md",
                translation="translations/ja/docs/other.md",
            )
            with self.assertRaisesRegex(
                TranslationError,
                "is not a published canonical document",
            ):
                validate(root)

    def test_guided_surface_requires_index_md(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-translation-") as directory:
            root = Path(directory)
            canonical = prepare_translation(root)
            write_manifest(
                root,
                sha=blob_sha(canonical),
                surfaces=["guided"],
            )
            with self.assertRaisesRegex(
                TranslationError,
                "must be an index.md document for guided use",
            ):
                validate(root)

    def test_guided_index_need_not_be_in_publication_catalog(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-translation-") as directory:
            root = Path(directory)
            prepare_translation(root)
            (root / "translations" / "ja" / "README.md").unlink()

            canonical = b"# Composition documentation index\n"
            (root / "docs" / "index.md").write_bytes(canonical)
            (root / "translations" / "ja" / "docs").mkdir(parents=True)
            (root / "translations" / "ja" / "docs" / "index.md").write_text(
                "# Composition documentation index\n\n"
                "> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            write_manifest(
                root,
                sha=blob_sha(canonical),
                canonical="docs/index.md",
                translation="translations/ja/docs/index.md",
                surfaces=["guided"],
            )

            result = validate(root)
            self.assertIn("translations validated: 1", result)
            self.assertIn("reader translations: 0", result)
            self.assertIn("guided translations: 1", result)

    def test_duplicate_canonical_language_pair_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-translation-") as directory:
            root = Path(directory)
            canonical = prepare_translation(root)
            entry = {
                "canonical": "README.md",
                "language": "ja",
                "translation": "translations/ja/README.md",
                "canonical_blob_sha": blob_sha(canonical),
                "surfaces": ["reader"],
            }
            (root / "translations" / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "canonical_language": "en",
                        "translations": [entry, dict(entry)],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                TranslationError,
                "duplicate canonical/language translation pair",
            ):
                validate(root)

    def test_translation_path_must_mirror_canonical_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-translation-") as directory:
            root = Path(directory)
            canonical = prepare_translation(root)
            (root / "translations" / "ja" / "overview.md").write_text(
                "# Composition\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            write_manifest(
                root,
                sha=blob_sha(canonical),
                translation="translations/ja/overview.md",
            )
            with self.assertRaisesRegex(TranslationError, "must mirror the canonical path"):
                validate(root)

    def test_unknown_surface_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-translation-") as directory:
            root = Path(directory)
            canonical = prepare_translation(root)
            write_manifest(root, sha=blob_sha(canonical), surfaces=["search"])
            with self.assertRaisesRegex(TranslationError, "must be one of reader or guided"):
                validate(root)

    def test_missing_translation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-translation-") as directory:
            root = Path(directory)
            canonical = prepare_translation(root)
            (root / "translations" / "ja" / "README.md").unlink()
            write_manifest(root, sha=blob_sha(canonical))
            with self.assertRaisesRegex(TranslationError, "must be an existing regular file"):
                validate(root)

    def test_japanese_notice_is_required_after_title(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-translation-") as directory:
            root = Path(directory)
            canonical = prepare_translation(root)
            (root / "translations" / "ja" / "README.md").write_text(
                "# Composition\n\nTranslation without notice.\n",
                encoding="utf-8",
            )
            write_manifest(root, sha=blob_sha(canonical))
            with self.assertRaisesRegex(
                TranslationError,
                "must place the non-authoritative notice immediately after",
            ):
                validate(root)

    def test_undeclared_translation_markdown_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-translation-") as directory:
            root = Path(directory)
            canonical = prepare_translation(root)
            (root / "translations" / "ja" / "extra.md").write_text(
                "# Extra\n\n> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            write_manifest(root, sha=blob_sha(canonical))
            with self.assertRaisesRegex(TranslationError, "undeclared translation Markdown"):
                validate(root)


if __name__ == "__main__":
    unittest.main()
