from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePosixPath

from scripts import publish_translations as translation_publisher
from scripts.assemble_publications import load_manifest, pages
from scripts.assemble_publications_v3 import load_catalog


ROOT = Path(__file__).resolve().parents[1]


class CompositionModelTranslationIntegrationTests(unittest.TestCase):
    def test_locked_provider_publishes_japanese_composition_model(self) -> None:
        provider = ROOT.parent / "composition-source"
        if not provider.is_dir():
            self.skipTest("Composition provider checkout is only available in Pages CI")

        documents, assets = load_catalog("composition", provider.resolve(strict=True))
        _, navigation = load_manifest(ROOT / "site-manifest.json")
        composition_pages = [
            page for page in pages(navigation) if page["publication"] == "composition"
        ]

        with tempfile.TemporaryDirectory() as directory:
            docs_root = Path(directory) / "docs"
            records = translation_publisher.publish_translations(
                {"composition": (provider, documents, assets)},
                composition_pages,
                docs_root,
                skip_stale=True,
            )

            model_record = next(
                record
                for record in records
                if record.canonical_source
                == PurePosixPath("docs/architecture/composition-model.md")
            )
            self.assertEqual(model_record.language, "ja")
            self.assertEqual(
                model_record.translation_destination,
                PurePosixPath("ja/composition/architecture/composition-model.md"),
            )

            model = (
                docs_root
                / "ja"
                / "composition"
                / "architecture"
                / "composition-model.md"
            )
            self.assertTrue(model.is_file())
            self.assertIn("# Composition モデル", model.read_text(encoding="utf-8"))

            index = docs_root / "ja" / "composition" / "docs" / "index.md"
            self.assertTrue(index.is_file())
            self.assertIn(
                "[Composition model](../architecture/composition-model.md)",
                index.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
