#!/usr/bin/env python3
"""Regression coverage for the reader document's runtime mount and layout boundary."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "docs" / "composition-playground.md"
LANDING = ROOT / "docs" / "landing.md"
JAPANESE_LANDING = ROOT / "translations" / "ja" / "docs" / "landing.md"
STYLESHEET = ROOT / "assets" / "stylesheets" / "composition-playground.css"


class CompositionPlaygroundDocumentTests(unittest.TestCase):
    def test_markdown_heading_does_not_collide_with_runtime_root_id(self) -> None:
        text = DOCUMENT.read_text(encoding="utf-8")
        heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        self.assertIsNotNone(heading)
        heading_slug = re.sub(r"[^a-z0-9 -]", "", heading.group(1).lower())
        heading_slug = re.sub(r"[ -]+", "-", heading_slug).strip("-")
        explicit_ids = re.findall(r'\bid="([^"]+)"', text)
        self.assertIn("composition-playground", explicit_ids)
        self.assertNotEqual(
            heading_slug,
            "composition-playground",
            "the rendered h1 id would shadow the interactive Playground root",
        )

    def test_landing_pages_link_to_playground(self) -> None:
        canonical = LANDING.read_text(encoding="utf-8")
        japanese = JAPANESE_LANDING.read_text(encoding="utf-8")

        self.assertGreaterEqual(canonical.count('href="playground/"'), 2)
        self.assertGreaterEqual(japanese.count('href="/playground/"'), 2)
        self.assertIn("Try Composition Playground", canonical)
        self.assertIn("Composition Playground を試す", japanese)

    def test_playground_grid_tracks_can_shrink_inside_reader_content(self) -> None:
        css = STYLESHEET.read_text(encoding="utf-8")
        self.assertRegex(
            css,
            r"\.composition-playground\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)",
        )
        self.assertRegex(
            css,
            r"\.composition-playground \[data-playground-app\]\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)",
        )
        self.assertRegex(
            css,
            r"\.composition-playground\s*>\s*\*,\s*\.composition-playground \[data-playground-app\]\s*>\s*\*\s*\{[^}]*min-inline-size:\s*0",
        )


if __name__ == "__main__":
    unittest.main()
