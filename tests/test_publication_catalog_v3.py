from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_publication_catalog import CatalogError, validate_catalog


class PublicationCatalogV3Tests(unittest.TestCase):
    def prepare(self, root: Path) -> Path:
        (root / "docs").mkdir(parents=True)
        (root / "README.md").write_text("# Home\n", encoding="utf-8")
        (root / "docs/glossary.yml").write_text(
            "schema_version: 1\nterms:\n  - id: templates-example\n"
            "    term: Example\n    origin: repository\n"
            "    definition: Example definition.\n",
            encoding="utf-8",
        )
        path = root / "docs/publication-catalog.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "documents": [
                        {
                            "id": "overview",
                            "source": "README.md",
                            "optional": False,
                            "home": True,
                        }
                    ],
                    "assets": [],
                    "glossary": {"source": "docs/glossary.yml"},
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_valid_v3_glossary_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.prepare(root)
            documents, assets = validate_catalog(catalog, root)
        self.assertEqual(["overview"], [item.document_id for item in documents])
        self.assertEqual([], assets)

    def test_glossary_must_be_yml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.prepare(root)
            data = json.loads(catalog.read_text(encoding="utf-8"))
            data["glossary"] = {"source": "README.md"}
            catalog.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(CatalogError, "must be a \\.yml file"):
                validate_catalog(catalog, root)

    def test_glossary_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.prepare(root)
            glossary = root / "docs/glossary.yml"
            glossary.unlink()
            glossary.symlink_to(root / "README.md")
            with self.assertRaisesRegex(CatalogError, "symbolic link"):
                validate_catalog(catalog, root)

    def test_glossary_must_not_overlap_asset_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.prepare(root)
            data = json.loads(catalog.read_text(encoding="utf-8"))
            data["assets"] = [
                {
                    "source": "docs/glossary.yml",
                    "destination": "glossary-source.yml",
                    "optional": False,
                }
            ]
            catalog.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(CatalogError, "must not overlap"):
                validate_catalog(catalog, root)


if __name__ == "__main__":
    unittest.main()
