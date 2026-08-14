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

    def rewrite(self, catalog: Path, **changes: object) -> None:
        data = json.loads(catalog.read_text(encoding="utf-8"))
        data.update(changes)
        catalog.write_text(json.dumps(data), encoding="utf-8")

    def test_valid_v3_glossary_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.prepare(root)
            documents, assets = validate_catalog(catalog, root)
        self.assertEqual(["overview"], [item.document_id for item in documents])
        self.assertEqual([], assets)

    def test_v3_catalog_without_glossary_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.prepare(root)
            data = json.loads(catalog.read_text(encoding="utf-8"))
            del data["glossary"]
            catalog.write_text(json.dumps(data), encoding="utf-8")
            documents, assets = validate_catalog(catalog, root)
        self.assertEqual(["overview"], [item.document_id for item in documents])
        self.assertEqual([], assets)

    def test_glossary_rejected_on_version_2(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.prepare(root)
            self.rewrite(catalog, schema_version=2)
            with self.assertRaisesRegex(CatalogError, "requires schema_version 3"):
                validate_catalog(catalog, root)

    def test_glossary_must_be_object(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.prepare(root)
            self.rewrite(catalog, glossary=["docs/glossary.yml"])
            with self.assertRaisesRegex(CatalogError, "glossary must be an object"):
                validate_catalog(catalog, root)

    def test_glossary_must_have_exactly_source_field(self) -> None:
        for glossary in ({}, {"source": "docs/glossary.yml", "extra": True}):
            with self.subTest(glossary=glossary), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                catalog = self.prepare(root)
                self.rewrite(catalog, glossary=glossary)
                with self.assertRaisesRegex(CatalogError, "exactly the source field"):
                    validate_catalog(catalog, root)

    def test_glossary_must_be_yml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.prepare(root)
            self.rewrite(catalog, glossary={"source": "README.md"})
            with self.assertRaisesRegex(CatalogError, "must be a \\.yml file"):
                validate_catalog(catalog, root)

    def test_nonexistent_glossary_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.prepare(root)
            self.rewrite(catalog, glossary={"source": "docs/missing.yml"})
            with self.assertRaisesRegex(CatalogError, "not a regular file"):
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
            self.rewrite(
                catalog,
                assets=[
                    {
                        "source": "docs/glossary.yml",
                        "destination": "glossary-source.yml",
                        "optional": False,
                    }
                ],
            )
            with self.assertRaisesRegex(CatalogError, "must not overlap"):
                validate_catalog(catalog, root)

    def test_repository_declares_expected_glossary(self) -> None:
        root = Path(__file__).resolve().parents[1]
        data = json.loads(
            (root / "docs/publication-catalog.json").read_text(encoding="utf-8")
        )
        self.assertEqual(3, data["schema_version"])
        self.assertEqual({"source": "docs/glossary.yml"}, data["glossary"])


if __name__ == "__main__":
    unittest.main()
