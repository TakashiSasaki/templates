from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from scripts.assemble_publications import load_manifest, pages
from scripts.assemble_publications_v3 import load_catalog
from scripts.prepare_repository_tree_publication import PreparationError, prepare
from scripts.publish_translations import publish_translations
from scripts.translation_coverage import build_reader_coverage
from scripts.translation_manifest import load_translation_manifest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CANONICALS = {
    PurePosixPath("docs/landing.md"),
    PurePosixPath("docs/policy-composition-coexistence.md"),
    PurePosixPath("docs/capabilities.md"),
    PurePosixPath("docs/lifecycle.md"),
}


def copy_site_fixture(root: Path, *, translations: bool) -> None:
    shutil.copytree(ROOT / "docs", root / "docs")
    shutil.copy2(ROOT / "site-manifest.json", root / "site-manifest.json")
    shutil.copy2(ROOT / "zensical.template.toml", root / "zensical.template.toml")
    if translations:
        shutil.copytree(ROOT / "translations", root / "translations")


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

    def test_site_reader_manifest_declares_site_owned_documents(self) -> None:
        documents, _, _ = self.site_publication()
        catalog_sources = {document["source"] for document in documents.values()}
        manifest = load_translation_manifest(
            ROOT / "translations" / "manifest.json",
            "site translation manifest",
            publication_root=ROOT,
        )
        reader_entries = manifest.for_surface("reader")
        declared = {entry.canonical for entry in reader_entries}

        self.assertTrue(EXPECTED_CANONICALS.issubset(declared))
        self.assertTrue(declared.issubset(catalog_sources))
        for entry in reader_entries:
            with self.subTest(canonical=entry.canonical.as_posix()):
                self.assertIsNotNone(entry.current_blob_sha)

    def test_site_reader_coverage_reflects_manifest_freshness(self) -> None:
        documents, assets, included_pages = self.site_publication()
        manifest = load_translation_manifest(
            ROOT / "translations" / "manifest.json",
            "site translation manifest",
            publication_root=ROOT,
        )
        expected_status = {
            entry.canonical.as_posix(): entry.freshness
            for entry in manifest.for_surface("reader")
        }

        coverage = build_reader_coverage(
            {"site": (ROOT, documents, assets)},
            included_pages,
        )
        site_ja_records = {
            record["canonical_source"]: record["status"]
            for record in coverage["records"]
            if record["publication"] == "site" and record["language"] == "ja"
        }

        for canonical in EXPECTED_CANONICALS:
            with self.subTest(canonical=canonical.as_posix()):
                self.assertEqual(
                    site_ja_records[canonical.as_posix()],
                    expected_status[canonical.as_posix()],
                )

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

    def test_preparation_allows_site_without_translations_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site_root = base / "site"
            site_root.mkdir()
            copy_site_fixture(site_root, translations=False)
            prepared = base / "prepared"

            prepare(site_root, prepared)

            self.assertFalse((prepared / "translations").exists())

    def test_site_reader_publication_matches_current_availability(self) -> None:
        documents, assets, included_pages = self.site_publication()
        manifest = load_translation_manifest(
            ROOT / "translations" / "manifest.json",
            "site translation manifest",
            publication_root=ROOT,
        )
        source_to_document = {
            document["source"]: document_id
            for document_id, document in documents.items()
        }
        page_destinations = {
            (page["publication"], page["document"]): page["destination"]
            for page in included_pages
        }
        expected = {
            PurePosixPath(entry.language)
            / page_destinations[("site", source_to_document[entry.canonical])]
            for entry in manifest.for_surface("reader")
            if entry.is_current
        }

        with tempfile.TemporaryDirectory() as directory:
            docs_root = Path(directory) / "docs"
            docs_root.mkdir()
            records = publish_translations(
                {"site": (ROOT, documents, assets)},
                included_pages,
                docs_root,
                skip_stale=True,
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

    def test_stale_site_translation_is_omitted_without_touching_english(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site_root = base / "site"
            site_root.mkdir()
            copy_site_fixture(site_root, translations=True)
            landing = site_root / "docs" / "landing.md"
            landing.write_text(
                landing.read_text(encoding="utf-8") + "\n<!-- canonical changed -->\n",
                encoding="utf-8",
            )

            documents, assets = load_catalog("site", site_root)
            _, navigation = load_manifest(site_root / "site-manifest.json")
            included_pages = [
                page
                for page in pages(navigation)
                if page["publication"] == "site"
            ]
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)
            english = docs_root / "index.md"
            english.write_text("# Canonical English\n", encoding="utf-8")

            records = publish_translations(
                {"site": (site_root, documents, assets)},
                included_pages,
                docs_root,
                skip_stale=True,
            )

            self.assertEqual(len(records), 3)
            self.assertFalse((docs_root / "ja" / "index.md").exists())
            self.assertEqual(
                english.read_text(encoding="utf-8"),
                "# Canonical English\n",
            )
            self.assertNotIn(
                PurePosixPath("docs/landing.md"),
                {record.canonical_source for record in records},
            )

    @unittest.skipIf(os.name == "nt", "symlink creation is not reliably available on Windows")
    def test_preparation_rejects_broken_symlinked_translations_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site_root = base / "site"
            site_root.mkdir()
            copy_site_fixture(site_root, translations=False)
            (site_root / "translations").symlink_to(
                base / "missing-translations",
                target_is_directory=True,
            )

            with self.assertRaisesRegex(
                PreparationError,
                "site translations must not be a symlink",
            ):
                prepare(site_root, base / "prepared")

    @unittest.skipIf(os.name == "nt", "symlink creation is not reliably available on Windows")
    def test_preparation_rejects_symlink_inside_translations_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site_root = base / "site"
            site_root.mkdir()
            copy_site_fixture(site_root, translations=True)
            translated_landing = (
                site_root / "translations" / "ja" / "docs" / "landing.md"
            )
            translated_landing.unlink()
            external = base / "external-landing.md"
            external.write_text("# External\n", encoding="utf-8")
            translated_landing.symlink_to(external)

            with self.assertRaisesRegex(
                PreparationError,
                "site translations contains a symlink",
            ):
                prepare(site_root, base / "prepared")


if __name__ == "__main__":
    unittest.main()
