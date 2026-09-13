"""Regression checks for the Composition-provider maintenance overview."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "provider-maintenance.md"
INDEX = ROOT / "docs" / "index.md"
RELEASE = ROOT / "release" / "README.md"


class ProviderMaintenanceDocumentationTests(unittest.TestCase):
    def test_overview_has_stable_provider_scope_and_canonical_links(self) -> None:
        text = GUIDE.read_text(encoding="utf-8")
        self.assertIn("Composition authority", text)
        self.assertIn("not guidance for maintaining a", text)
        for target in (
            "../catalog/README.md",
            "architecture/catalog.md",
            "architecture/composer-mvp.md",
            "reference/composer.md",
            "../schemas/README.md",
            "evaluation-guide.md",
            "publication-catalog.md",
            "../release/README.md",
        ):
            self.assertIn(target, text)
        self.assertNotIn("Use templates", text)
        self.assertNotIn("Maintain templates", text)

    def test_index_and_installer_record_preserve_consumer_boundary(self) -> None:
        self.assertIn("provider-maintenance.md", INDEX.read_text(encoding="utf-8"))
        release = RELEASE.read_text(encoding="utf-8")
        self.assertIn("Provider release record versus consumer use", release)
        self.assertIn("`composition-installer.json` remains the machine-readable authority", release)
        self.assertIn("../docs/consumer-guide.md", release)


if __name__ == "__main__":
    unittest.main()
