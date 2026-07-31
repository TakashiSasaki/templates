#!/usr/bin/env python3
"""Focused publication catalog schema-version tests."""

from __future__ import annotations

import json
import runpy
import tempfile
import unittest
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
ASSEMBLER = runpy.run_path(str(SITE_ROOT / "scripts" / "assemble_docs.py"))
AssemblyError = ASSEMBLER["AssemblyError"]
load_publication_catalog = ASSEMBLER["load_publication_catalog"]


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
            path = Path(directory) / "publication-catalog.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            with self.assertRaisesRegex(
                AssemblyError,
                "schema_version must be the integer 1",
            ):
                load_publication_catalog(path)


if __name__ == "__main__":
    unittest.main()
