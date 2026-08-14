#!/usr/bin/env python3
"""Focused publication catalog schema-version tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.assemble_publications_v3 import AssemblyError, load_catalog
from scripts.prepare_repository_tree_publication import augment_catalog


class PublicationCatalogSchemaVersionTests(unittest.TestCase):
    def write_catalog(self, root: Path, catalog: dict) -> None:
        path = root / "docs" / "publication-catalog.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(catalog), encoding="utf-8")

    def base_catalog(self, version: int) -> dict:
        return {
            "schema_version": version,
            "documents": [
                {
                    "id": "overview",
                    "source": "README.md",
                    "optional": False,
                    "home": True,
                }
            ],
        }

    def write_glossary(self, root: Path) -> None:
        (root / "docs" / "glossary.yml").write_text(
            "schema_version: 1\n"
            "terms:\n"
            "  - id: templates-example\n"
            "    term: Example\n"
            "    origin: repository\n"
            "    definition: Example term.\n",
            encoding="utf-8",
        )

    def test_boolean_schema_version_is_rejected(self) -> None:
        catalog = self.base_catalog(True)
        with tempfile.TemporaryDirectory(prefix="catalog-version-test-") as directory:
            root = Path(directory)
            self.write_catalog(root, catalog)
            with self.assertRaisesRegex(
                AssemblyError,
                "test catalog schema_version must be integer 1, 2, or 3",
            ):
                load_catalog("test", root)

    def test_schema_v3_accepts_declared_glossary(self) -> None:
        catalog = self.base_catalog(3)
        catalog["glossary"] = {"source": "docs/glossary.yml"}
        with tempfile.TemporaryDirectory(prefix="catalog-version-test-") as directory:
            root = Path(directory)
            self.write_catalog(root, catalog)
            self.write_glossary(root)
            documents, assets = load_catalog("test", root)
            self.assertIn("overview", documents)
            self.assertEqual(assets, [])

    def test_schema_v3_allows_omitting_glossary(self) -> None:
        catalog = self.base_catalog(3)
        with tempfile.TemporaryDirectory(prefix="catalog-version-test-") as directory:
            root = Path(directory)
            self.write_catalog(root, catalog)
            documents, assets = load_catalog("test", root)
            self.assertIn("overview", documents)
            self.assertEqual(assets, [])

    def test_schema_v2_rejects_glossary_field(self) -> None:
        catalog = self.base_catalog(2)
        catalog["glossary"] = {"source": "docs/glossary.yml"}
        with tempfile.TemporaryDirectory(prefix="catalog-version-test-") as directory:
            root = Path(directory)
            self.write_catalog(root, catalog)
            with self.assertRaisesRegex(AssemblyError, "unsupported fields: glossary"):
                load_catalog("test", root)

    def test_schema_v3_rejects_null_glossary(self) -> None:
        catalog = self.base_catalog(3)
        catalog["glossary"] = None
        with tempfile.TemporaryDirectory(prefix="catalog-version-test-") as directory:
            root = Path(directory)
            self.write_catalog(root, catalog)
            with self.assertRaisesRegex(AssemblyError, "glossary is invalid"):
                load_catalog("test", root)

    def test_glossary_source_must_not_overlap_assets(self) -> None:
        catalog = self.base_catalog(3)
        catalog["glossary"] = {"source": "docs/glossary.yml"}
        catalog["assets"] = [
            {
                "source": "docs/glossary.yml",
                "destination": "raw-glossary.yml",
                "optional": False,
            }
        ]
        with tempfile.TemporaryDirectory(prefix="catalog-version-test-") as directory:
            root = Path(directory)
            self.write_catalog(root, catalog)
            self.write_glossary(root)
            with self.assertRaisesRegex(
                AssemblyError,
                "glossary source must not overlap asset sources",
            ):
                load_catalog("test", root)

    def test_repository_tree_preparation_preserves_glossary_declaration(self) -> None:
        catalog = self.base_catalog(3)
        catalog["glossary"] = {"source": "docs/glossary.yml"}
        prepared = augment_catalog(catalog, ())
        self.assertEqual(
            prepared["glossary"],
            {"source": "docs/glossary.yml"},
        )
        self.assertEqual(catalog["documents"], prepared["documents"])


if __name__ == "__main__":
    unittest.main()
