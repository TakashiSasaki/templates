#!/usr/bin/env python3
"""Focused duplicate JSON member rejection tests."""

from __future__ import annotations

import runpy
import tempfile
import unittest
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
ASSEMBLER = runpy.run_path(str(SITE_ROOT / "scripts" / "assemble_docs.py"))
AssemblyError = ASSEMBLER["AssemblyError"]
load_manifest = ASSEMBLER["load_manifest"]
load_publication_catalog = ASSEMBLER["load_publication_catalog"]


class DuplicateJsonMemberTests(unittest.TestCase):
    def write(self, directory: str, name: str, content: str) -> Path:
        path = Path(directory) / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_catalog_duplicate_member_is_rejected(self) -> None:
        content = (
            '{"schema_version":1,"documents":['
            '{"id":"overview","source":"README.md","source":"HOME.md",'
            '"optional":false,"home":true}]}'
        )
        with tempfile.TemporaryDirectory(prefix="duplicate-catalog-test-") as directory:
            path = self.write(directory, "publication-catalog.json", content)
            with self.assertRaisesRegex(
                AssemblyError,
                "publication catalog contains duplicate object member: source",
            ):
                load_publication_catalog(path)

    def test_manifest_duplicate_member_is_rejected(self) -> None:
        content = (
            '{"navigation":['
            '{"title":"Overview","document":"overview","document":"other",'
            '"destination":"index.md"}]}'
        )
        with tempfile.TemporaryDirectory(prefix="duplicate-manifest-test-") as directory:
            path = self.write(directory, "site-manifest.json", content)
            with self.assertRaisesRegex(
                AssemblyError,
                "site manifest contains duplicate object member: document",
            ):
                load_manifest(path)


if __name__ == "__main__":
    unittest.main()
