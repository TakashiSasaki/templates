#!/usr/bin/env python3
"""Focused duplicate JSON member rejection tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.assemble_publications import AssemblyError, load_catalog, load_manifest


class DuplicateJsonMemberTests(unittest.TestCase):
    def test_catalog_duplicate_member_is_rejected(self) -> None:
        content = (
            '{"schema_version":1,"documents":['
            '{"id":"overview","source":"README.md","source":"HOME.md",'
            '"optional":false,"home":true}]}'
        )
        with tempfile.TemporaryDirectory(prefix="duplicate-catalog-test-") as directory:
            root = Path(directory)
            catalog = root / "docs" / "publication-catalog.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(content, encoding="utf-8")

            with self.assertRaisesRegex(
                AssemblyError,
                "test catalog contains duplicate member: source",
            ):
                load_catalog("test", root)

    def test_manifest_duplicate_member_is_rejected(self) -> None:
        content = (
            '{"schema_version":2,'
            '"home":{"publication":"site","document":"portal-home"},'
            '"navigation":['
            '{"title":"Home","publication":"site",'
            '"document":"portal-home","document":"other",'
            '"destination":"index.md"}]}'
        )
        with tempfile.TemporaryDirectory(prefix="duplicate-manifest-test-") as directory:
            path = Path(directory) / "site-manifest.json"
            path.write_text(content, encoding="utf-8")

            with self.assertRaisesRegex(
                AssemblyError,
                "site manifest contains duplicate member: document",
            ):
                load_manifest(path)


if __name__ == "__main__":
    unittest.main()
