from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from typing import Any

from scripts.publish_translations import (
    TranslationPublicationError,
    publish_translations,
)
from scripts.translation_coverage import (
    TranslationCoverageError,
    build_reader_coverage,
)


def blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object identity


class TranslationAvailabilityTests(unittest.TestCase):
    def prepare(
        self,
        root: Path,
        *,
        stale: bool = True,
    ) -> tuple[
        dict[str, tuple[Path, dict[str, dict[str, Any]], list[dict[str, Any]]]],
        list[dict[str, Any]],
    ]:
        (root / "docs").mkdir(parents=True)
        (root / "translations" / "ja" / "docs").mkdir(parents=True)
        translated_bytes = b"# Translated\n"
        missing_bytes = b"# Missing translation\n"
        (root / "docs" / "translated.md").write_bytes(translated_bytes)
        (root / "docs" / "missing.md").write_bytes(missing_bytes)
        (root / "translations" / "ja" / "docs" / "translated.md").write_text(
            "# 翻訳\n\n> **参考訳（非正本）:** test\n",
            encoding="utf-8",
        )
        recorded = "0" * 40 if stale else blob_sha(translated_bytes)
        (root / "translations" / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "canonical_language": "en",
                    "translations": [
                        {
                            "canonical": "docs/translated.md",
                            "language": "ja",
                            "translation": "translations/ja/docs/translated.md",
                            "canonical_blob_sha": recorded,
                            "surfaces": ["reader"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        documents = {
            "translated": {
                "source": PurePosixPath("docs/translated.md"),
                "optional": False,
                "home": False,
            },
            "missing": {
                "source": PurePosixPath("docs/missing.md"),
                "optional": False,
                "home": False,
            },
        }
        pages = [
            {
                "publication": "policy",
                "document": "translated",
                "destination": PurePosixPath("policy/translated.md"),
            },
            {
                "publication": "policy",
                "document": "missing",
                "destination": PurePosixPath("policy/missing.md"),
            },
        ]
        return {"policy": (root, documents, [])}, pages

    def test_strict_caller_still_rejects_stale_translation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            publications, pages = self.prepare(base / "policy", stale=True)
            docs_root = base / "output"
            docs_root.mkdir()
            with self.assertRaisesRegex(TranslationPublicationError, "stale translation"):
                publish_translations(publications, pages, docs_root)

    def test_integrated_availability_mode_skips_only_stale_translation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            publications, pages = self.prepare(base / "policy", stale=True)
            docs_root = base / "output"
            docs_root.mkdir()
            records = publish_translations(
                publications,
                pages,
                docs_root,
                skip_stale=True,
            )
            self.assertEqual(records, [])
            self.assertFalse((docs_root / "ja" / "policy" / "translated.md").exists())

    def test_current_translation_still_publishes_in_availability_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            publications, pages = self.prepare(base / "policy", stale=False)
            docs_root = base / "output"
            docs_root.mkdir()
            records = publish_translations(
                publications,
                pages,
                docs_root,
                skip_stale=True,
            )
            self.assertEqual(len(records), 1)
            self.assertTrue((docs_root / "ja" / "policy" / "translated.md").is_file())

    def test_reader_coverage_distinguishes_stale_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            publications, pages = self.prepare(Path(directory) / "policy", stale=True)
            coverage = build_reader_coverage(publications, pages)
            self.assertEqual(coverage["languages"], ["ja"])
            self.assertEqual(
                coverage["summary"],
                {"current": 0, "stale": 1, "missing": 1},
            )
            statuses = {
                record["document"]: record["status"]
                for record in coverage["records"]
            }
            self.assertEqual(
                statuses,
                {"translated": "stale", "missing": "missing"},
            )

    def test_stale_declaration_outside_reader_site_is_still_structurally_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "policy"
            publications, pages = self.prepare(root, stale=True)
            pages = [page for page in pages if page["document"] != "translated"]
            with self.assertRaisesRegex(
                TranslationCoverageError,
                "not included in the assembled site",
            ):
                build_reader_coverage(publications, pages)


if __name__ == "__main__":
    unittest.main()
