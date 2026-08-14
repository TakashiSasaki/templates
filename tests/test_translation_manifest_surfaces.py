from __future__ import annotations

import unittest

from scripts.translation_manifest_surfaces import (
    TranslationManifestSurfaceError,
    project_reader_manifest,
)


class TranslationManifestSurfaceTests(unittest.TestCase):
    def test_schema_v2_projects_only_reader_entries(self) -> None:
        manifest = {
            "schema_version": 2,
            "canonical_language": "en",
            "translations": [
                {
                    "canonical": "docs/index.md",
                    "language": "ja",
                    "translation": "translations/ja/docs/index.md",
                    "canonical_blob_sha": "1" * 40,
                    "surfaces": ["guided"],
                },
                {
                    "canonical": "docs/reader.md",
                    "language": "ja",
                    "translation": "translations/ja/docs/reader.md",
                    "canonical_blob_sha": "2" * 40,
                    "surfaces": ["reader", "guided"],
                },
            ],
        }
        projected = project_reader_manifest(manifest, "policy translation manifest")
        self.assertEqual(projected["schema_version"], 1)
        self.assertEqual(len(projected["translations"]), 1)
        self.assertEqual(projected["translations"][0]["canonical"], "docs/reader.md")
        self.assertNotIn("surfaces", projected["translations"][0])

    def test_schema_v1_remains_reader_only_during_migration(self) -> None:
        manifest = {
            "schema_version": 1,
            "canonical_language": "en",
            "translations": [],
        }
        self.assertIs(project_reader_manifest(manifest, "manifest"), manifest)

    def test_invalid_surface_declarations_fail_closed(self) -> None:
        base = {
            "canonical": "docs/index.md",
            "language": "ja",
            "translation": "translations/ja/docs/index.md",
            "canonical_blob_sha": "1" * 40,
        }
        for value in ([], ["search"], ["guided", "guided"]):
            with self.subTest(value=value):
                manifest = {
                    "schema_version": 2,
                    "canonical_language": "en",
                    "translations": [{**base, "surfaces": value}],
                }
                with self.assertRaises(TranslationManifestSurfaceError):
                    project_reader_manifest(manifest, "manifest")


if __name__ == "__main__":
    unittest.main()
