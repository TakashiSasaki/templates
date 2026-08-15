from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.glossary import GlossaryError, glossary_source_from_catalog


class GlossaryCatalogV3OnlyTests(unittest.TestCase):
    def write_catalog(self, root: Path, schema_version: object) -> None:
        docs = root / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "publication-catalog.json").write_text(
            json.dumps(
                {
                    "schema_version": schema_version,
                    "documents": [
                        {
                            "id": "overview",
                            "source": "README.md",
                            "optional": False,
                            "home": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_retired_catalog_versions_are_rejected(self) -> None:
        for version in (1, 2):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write_catalog(root, version)
                with self.assertRaisesRegex(
                    GlossaryError,
                    "publication catalog schema_version must be integer 3",
                ):
                    glossary_source_from_catalog(root)

    def test_invalid_catalog_versions_are_rejected(self) -> None:
        for version in (True, 4, "3", 3.0, None):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write_catalog(root, version)
                with self.assertRaisesRegex(
                    GlossaryError,
                    "publication catalog schema_version must be integer 3",
                ):
                    glossary_source_from_catalog(root)

    def test_schema_v3_without_glossary_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, 3)
            self.assertIsNone(glossary_source_from_catalog(root))


if __name__ == "__main__":
    unittest.main()
