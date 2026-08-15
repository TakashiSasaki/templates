from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.finalize_glossary_annotations import (
    RUNTIME_SCRIPT,
    RUNTIME_STYLE,
    annotate_site,
)


REVISION = "a" * 40


def model() -> dict[str, object]:
    return {
        "schema_version": 1,
        "repository": "TakashiSasaki/templates",
        "terms": [
            {
                "id": "templates-publication-catalog",
                "term": "Publication catalog",
                "aliases": [],
                "origin": "repository",
                "definition": "A provider-controlled publication declaration.",
                "provider": "site",
                "source_path": "docs/glossary.yml",
                "source_revision": REVISION,
            }
        ],
    }


class GlossaryInlineInjectionTests(unittest.TestCase):
    def test_standalone_annotated_page_receives_missing_runtime_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "glossary-model.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            annotated = root / "standalone" / "index.html"
            plain = root / "plain" / "index.html"
            annotated.parent.mkdir(parents=True)
            plain.parent.mkdir(parents=True)
            annotated.write_text(
                "<html><head></head><body><main>Publication catalog</main></body></html>",
                encoding="utf-8",
            )
            plain.write_text(
                "<html><head></head><body><main>No matching vocabulary.</main></body></html>",
                encoding="utf-8",
            )

            changed, links = annotate_site(root, glossary)

            self.assertEqual((changed, links), (1, 1))
            annotated_text = annotated.read_text(encoding="utf-8")
            plain_text = plain.read_text(encoding="utf-8")
            self.assertIn('data-glossary-id="templates-publication-catalog"', annotated_text)
            self.assertIn(RUNTIME_STYLE, annotated_text)
            self.assertIn(RUNTIME_SCRIPT, annotated_text)
            self.assertNotIn(RUNTIME_STYLE, plain_text)
            self.assertNotIn(RUNTIME_SCRIPT, plain_text)

    def test_global_asset_names_prevent_duplicate_runtime_injection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "glossary-model.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            page = root / "index.html"
            page.write_text(
                '<html><head><link rel="stylesheet" href="/stylesheets/glossary-inline.css">'
                '<script src="/javascripts/glossary-inline.js" defer></script></head>'
                '<body><main>Publication catalog</main></body></html>',
                encoding="utf-8",
            )

            changed, links = annotate_site(root, glossary)

            self.assertEqual((changed, links), (1, 1))
            rendered = page.read_text(encoding="utf-8")
            self.assertEqual(rendered.count("glossary-inline.css"), 1)
            self.assertEqual(rendered.count("glossary-inline.js"), 1)

    def test_guided_page_keeps_static_link_without_runtime_injection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "glossary-model.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            page = root / "guided" / "skill" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text(
                "<html><head></head><body><main>Publication catalog</main></body></html>",
                encoding="utf-8",
            )

            changed, links = annotate_site(root, glossary)

            self.assertEqual((changed, links), (1, 1))
            rendered = page.read_text(encoding="utf-8")
            self.assertIn('data-glossary-id="templates-publication-catalog"', rendered)
            self.assertNotIn(RUNTIME_STYLE, rendered)
            self.assertNotIn(RUNTIME_SCRIPT, rendered)

    def test_guided_filename_stem_also_keeps_static_link_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "glossary-model.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            page = root / "guided.html"
            page.write_text(
                "<html><head></head><body><main>Publication catalog</main></body></html>",
                encoding="utf-8",
            )

            changed, links = annotate_site(root, glossary)

            self.assertEqual((changed, links), (1, 1))
            rendered = page.read_text(encoding="utf-8")
            self.assertIn('data-glossary-id="templates-publication-catalog"', rendered)
            self.assertNotIn(RUNTIME_STYLE, rendered)
            self.assertNotIn(RUNTIME_SCRIPT, rendered)

    def test_headless_document_keeps_static_glossary_link_without_runtime_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "glossary-model.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            page = root / "index.html"
            page.write_text(
                "<html><body><main>Publication catalog</main></body></html>",
                encoding="utf-8",
            )

            changed, links = annotate_site(root, glossary)

            self.assertEqual((changed, links), (1, 1))
            rendered = page.read_text(encoding="utf-8")
            self.assertIn('data-glossary-id="templates-publication-catalog"', rendered)
            self.assertNotIn(RUNTIME_STYLE, rendered)
            self.assertNotIn(RUNTIME_SCRIPT, rendered)

    def test_second_finalization_is_idempotent_for_runtime_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "glossary-model.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            page = root / "standalone" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text(
                "<html><head></head><body><main>Publication catalog</main></body></html>",
                encoding="utf-8",
            )

            self.assertEqual(annotate_site(root, glossary), (1, 1))
            first = page.read_text(encoding="utf-8")
            self.assertEqual(annotate_site(root, glossary), (0, 0))
            second = page.read_text(encoding="utf-8")

            self.assertEqual(second, first)
            self.assertEqual(second.count(RUNTIME_STYLE), 1)
            self.assertEqual(second.count(RUNTIME_SCRIPT), 1)

    def test_existing_annotation_missing_runtime_assets_is_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "glossary-model.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            page = root / "standalone" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text(
                "<html><head></head><body><main>"
                '<a class="glossary-term" href="/glossary/#templates-publication-catalog" '
                'data-glossary-id="templates-publication-catalog">Publication catalog</a>'
                "</main></body></html>",
                encoding="utf-8",
            )

            changed, links = annotate_site(root, glossary)

            self.assertEqual((changed, links), (1, 0))
            rendered = page.read_text(encoding="utf-8")
            self.assertIn(RUNTIME_STYLE, rendered)
            self.assertIn(RUNTIME_SCRIPT, rendered)


if __name__ == "__main__":
    unittest.main()
