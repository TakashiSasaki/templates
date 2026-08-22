from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePosixPath

from scripts.assemble_publications import load_manifest, pages
from scripts.assemble_publications_v3 import load_catalog
from scripts.prepare_repository_tree_publication import prepare
from scripts.publish_translations import publish_translations
from scripts.translation_manifest import load_translation_manifest


ROOT = Path(__file__).resolve().parents[1]


class SiteOwnedTranslationContractTests(unittest.TestCase):
    def site_publication(self):
        documents, assets = load_catalog("site", ROOT)
        _, navigation = load_manifest(ROOT / "site-manifest.json")
        included_pages = [
            page
            for page in pages(navigation)
            if page["publication"] == "site"
        ]
        return documents, assets, included_pages

    def test_site_reader_manifest_covers_current_site_documents(self) -> None:
        documents, _, _ = self.site_publication()
        manifest = load_translation_manifest(
            ROOT / "translations" / "manifest.json",
            "site translation manifest",
            publication_root=ROOT,
        )
        reader_entries = manifest.for_surface("reader")

        self.assertEqual(
            {entry.canonical for entry in reader_entries},
            {document["source"] for document in documents.values()},
        )
        for entry in reader_entries:
            with self.subTest(canonical=entry.canonical.as_posix()):
                self.assertIsNotNone(entry.current_blob_sha)
                self.assertTrue(entry.is_current)

    def test_prepared_site_publication_preserves_translation_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prepared = Path(directory) / "site-publication"
            prepare(ROOT, prepared)

            self.assertEqual(
                (prepared / "translations" / "manifest.json").read_bytes(),
                (ROOT / "translations" / "manifest.json").read_bytes(),
            )
            self.assertEqual(
                (
                    prepared
                    / "translations"
                    / "ja"
                    / "docs"
                    / "landing.md"
                ).read_bytes(),
                (
                    ROOT
                    / "translations"
                    / "ja"
                    / "docs"
                    / "landing.md"
                ).read_bytes(),
            )

    def test_site_reader_translations_publish_under_ja_routes(self) -> None:
        documents, assets, included_pages = self.site_publication()
        expected = {
            PurePosixPath("ja/index.md"),
            PurePosixPath("ja/coexistence/index.md"),
            PurePosixPath("ja/capabilities/index.md"),
            PurePosixPath("ja/lifecycle/index.md"),
        }

        with tempfile.TemporaryDirectory() as directory:
            docs_root = Path(directory) / "docs"
            docs_root.mkdir()
            records = publish_translations(
                {"site": (ROOT, documents, assets)},
                included_pages,
                docs_root,
            )

            self.assertEqual(
                {record.translation_destination for record in records},
                expected,
            )
            for destination in expected:
                with self.subTest(destination=destination.as_posix()):
                    translated = docs_root.joinpath(*destination.parts)
                    self.assertTrue(translated.is_file())
                    self.assertIn(
                        "> **参考訳（非正本）:**",
                        translated.read_text(encoding="utf-8"),
                    )


if __name__ == "__main__":
    unittest.main()
