"""Regression coverage for Site-owned source declarations."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from scripts.validate_site_declarations import validate


ROOT = Path(__file__).resolve().parents[1]
PLAYGROUND_FILES = (
    "docs/publication-catalog.json",
    "integration-source.json",
    "tests/fixtures/composition-playground-v1.json",
    "zensical.template.toml",
    "docs/composition-playground.md",
    "assets/javascripts/composition-playground.js",
)


class WebsiteContractDeclarationTests(unittest.TestCase):
    def _checkout_sources(self) -> tuple[TemporaryDirectory[str], Path]:
        temporary = TemporaryDirectory()
        root = Path(temporary.name)
        for relative in PLAYGROUND_FILES:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        return temporary, root

    def test_current_playground_declarations_are_valid(self) -> None:
        self.assertEqual([], validate(ROOT))

    def test_publication_catalog_entry_is_required(self) -> None:
        temporary, root = self._checkout_sources()
        try:
            catalog_path = root / "docs/publication-catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["documents"][2]["source"] = "docs/retired-playground.md"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            errors = validate(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("exact composition-playground" in error for error in errors))

    def test_template_assets_are_required(self) -> None:
        temporary, root = self._checkout_sources()
        try:
            template_path = root / "zensical.template.toml"
            template = template_path.read_text(encoding="utf-8")
            template_path.write_text(
                template.replace('  "stylesheets/composition-playground.css"\n', ""),
                encoding="utf-8",
            )
            errors = validate(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("extra_css" in error for error in errors))

    def test_accessible_playground_markup_is_required(self) -> None:
        temporary, root = self._checkout_sources()
        try:
            page_path = root / "docs/composition-playground.md"
            page = page_path.read_text(encoding="utf-8")
            page_path.write_text(
                page.replace('aria-atomic="true"', 'aria-atomic="false"'),
                encoding="utf-8",
            )
            errors = validate(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("accessible validity status" in error for error in errors))

    def test_retired_javascript_tokens_are_rejected(self) -> None:
        temporary, root = self._checkout_sources()
        try:
            javascript_path = root / "assets/javascripts/composition-playground.js"
            javascript_path.write_text(
                javascript_path.read_text(encoding="utf-8") + "\n// expectedRevision\n",
                encoding="utf-8",
            )
            errors = validate(root)
        finally:
            temporary.cleanup()
        self.assertTrue(any("expectedRevision" in error for error in errors))
