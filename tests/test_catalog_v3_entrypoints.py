from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
TRANSLATION_PUBLISHER = ROOT / "scripts/publish_provider_translations.py"


class CatalogV3EntrypointTests(unittest.TestCase):
    def test_pages_build_uses_v3_catalog_entrypoint(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "python site-source/scripts/assemble_publications_v3.py",
            workflow,
        )
        self.assertNotIn(
            "python site-source/scripts/assemble_publications.py",
            workflow,
        )

    def test_translation_publisher_uses_v3_catalog_loader(self) -> None:
        source = TRANSLATION_PUBLISHER.read_text(encoding="utf-8")

        self.assertIn("from assemble_publications_v3 import load_catalog", source)
        self.assertNotIn("from assemble_publications import load_catalog", source)


if __name__ == "__main__":
    unittest.main()
