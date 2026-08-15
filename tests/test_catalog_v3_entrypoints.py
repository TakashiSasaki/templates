from __future__ import annotations

import unittest
from pathlib import Path

from scripts import assemble_publications, assemble_publications_v3


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
TRANSLATION_PUBLISHER = ROOT / "scripts/publish_provider_translations.py"


class CatalogV3EntrypointTests(unittest.TestCase):
    def test_pages_build_uses_stable_v3_alias(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "python site-source/scripts/assemble_publications_v3.py",
            workflow,
        )

    def test_stable_v3_alias_reexports_canonical_loader(self) -> None:
        self.assertIs(
            assemble_publications_v3.load_catalog,
            assemble_publications.load_catalog,
        )
        self.assertIs(
            assemble_publications_v3.main,
            assemble_publications.main,
        )

    def test_translation_publisher_uses_stable_v3_alias(self) -> None:
        source = TRANSLATION_PUBLISHER.read_text(encoding="utf-8")

        self.assertIn("from assemble_publications_v3 import load_catalog", source)


if __name__ == "__main__":
    unittest.main()
