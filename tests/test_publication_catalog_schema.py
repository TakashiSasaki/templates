#!/usr/bin/env python3
"""Focused publication catalog schema-version tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.assemble_publications_v3 import AssemblyError, load_catalog


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
            (root / "docs" / "glossary.yml").write_text(
                "schema_version: 1\n"
                "terms:\n"
                "  - id: templates-example\n"
                "    term: Example\n"
                "    origin: repository\n"
                "    definition: Example term.\n",
                encoding="utf-8",
            )
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


if __name__ == "__main__":
    unittest.main()
