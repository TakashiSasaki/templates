#!/usr/bin/env python3
"""Regression tests for the documentation-site manifest and assembly."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = SITE_ROOT / "site-manifest.json"
ASSEMBLER_PATH = SITE_ROOT / "scripts" / "assemble_docs.py"

PUBLISHED_CONTRACT_ORDER = (
    "README.md",
    "SKILL.md",
    "docs/skill-profiles.md",
    "docs/profile-contract-map.md",
    "INTERFACES.md",
    "CLI_INTERFACE.md",
    "MCP_INTERFACE.md",
    "WEB_INTERFACE.md",
    "RUNTIME.md",
)


class SiteAssemblyTests(unittest.TestCase):
    def load_pages(self) -> list[dict[str, object]]:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        pages = manifest.get("pages")
        self.assertIsInstance(pages, list)
        return pages

    def test_manifest_publishes_profile_contracts_in_expected_order(self) -> None:
        pages = self.load_pages()
        sources = [page["source"] for page in pages]
        destinations = [page["destination"] for page in pages]
        titles = [page["title"] for page in pages]

        self.assertEqual(len(sources), len(set(sources)), "source paths must be unique")
        self.assertEqual(
            len(destinations),
            len(set(destinations)),
            "destination paths must be unique",
        )
        self.assertEqual(len(titles), len(set(titles)), "navigation titles must be unique")

        positions = [sources.index(source) for source in PUBLISHED_CONTRACT_ORDER]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(destinations[0], "index.md")

    def test_assembly_copies_every_manifest_page_and_renders_navigation(self) -> None:
        pages = self.load_pages()

        with tempfile.TemporaryDirectory(prefix="site-assembly-test-") as directory:
            root = Path(directory)
            source_root = root / "canonical-source"
            output_root = root / "build"
            source_root.mkdir()

            for page in pages:
                source = source_root / str(page["source"])
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(f"# {page['title']}\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(ASSEMBLER_PATH),
                    "--source-root",
                    str(source_root),
                    "--site-root",
                    str(SITE_ROOT),
                    "--output-root",
                    str(output_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            generated_config = (output_root / "zensical.toml").read_text(
                encoding="utf-8"
            )
            for page in pages:
                destination = str(page["destination"])
                self.assertTrue(
                    (output_root / "docs" / destination).is_file(),
                    f"missing assembled page: {destination}",
                )
                self.assertIn(json.dumps(str(page["title"])), generated_config)
                self.assertIn(json.dumps(destination), generated_config)


if __name__ == "__main__":
    unittest.main()
