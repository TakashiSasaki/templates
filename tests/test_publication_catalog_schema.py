#!/usr/bin/env python3
"""Focused publication catalog schema-version tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.assemble_publications import AssemblyError, load_catalog


class PublicationCatalogSchemaVersionTests(unittest.TestCase):
    def test_boolean_schema_version_is_rejected(self) -> None:
        catalog = {
            "schema_version": True,
            "documents": [
                {
                    "id": "overview",
                    "source": "README.md",
                    "optional": False,
                    "home": True,
                }
            ],
        }
        with tempfile.TemporaryDirectory(prefix="catalog-version-test-") as directory:
            root = Path(directory)
            path = root / "docs" / "publication-catalog.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(catalog), encoding="utf-8")

            with self.assertRaisesRegex(
                AssemblyError,
                "test catalog schema_version must be integer 1 or 2",
            ):
                load_catalog("test", root)


if __name__ == "__main__":
    unittest.main()
