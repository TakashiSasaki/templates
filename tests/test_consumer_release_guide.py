from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "release-guide.md"
PUBLICATION = ROOT / "docs" / "publication-catalog.json"
TRANSLATIONS = ROOT / "translations" / "manifest.json"


class ConsumerReleaseGuideTests(unittest.TestCase):
    def test_release_guide_is_a_published_reader_document(self) -> None:
        publication = json.loads(PUBLICATION.read_text(encoding="utf-8"))
        documents = {entry["id"]: entry for entry in publication["documents"]}
        self.assertEqual(
            documents["release-guide"],
            {
                "id": "release-guide",
                "source": "docs/release-guide.md",
                "optional": False,
                "home": False,
            },
        )

        translations = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
        release_translation = next(
            entry
            for entry in translations["translations"]
            if entry["canonical"] == "docs/release-guide.md"
        )
        self.assertEqual(release_translation["language"], "ja")
        self.assertEqual(
            release_translation["translation"],
            "translations/ja/docs/release-guide.md",
        )
        self.assertEqual(release_translation["surfaces"], ["reader"])

    def test_release_guide_documents_the_managed_product_path(self) -> None:
        guide = GUIDE.read_text(encoding="utf-8")
        for required in (
            "contracts/implementation-evidence.json",
            "contracts/release-execution.json",
            ".template-composition/release/produce_release.py",
            "--revision <40-hex-revision>",
            "--recover-only",
            "fixed release argv",
            "same exact candidate revision",
            "validate_release_evidence.py",
            "validate_release_bundle.py",
        ):
            with self.subTest(required=required):
                self.assertIn(required, guide)

        self.assertIn("does not parse the human-readable command through a shell", guide)
        self.assertIn("standalone `produce_release_evidence.py`", guide)
        self.assertIn("not the normal consumer release path", guide)


if __name__ == "__main__":
    unittest.main()
