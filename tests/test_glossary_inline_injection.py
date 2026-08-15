from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.finalize_glossary_annotations import (
    RUNTIME_SCRIPT,
    RUNTIME_STYLE,
    GlossaryAnnotationFinalizeError,
    annotate_site,
)


REVISION = "a" * 40
GUIDED_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; manifest-src 'self'; "
    "base-uri 'none'; form-action 'none'; script-src 'self'"
)
GUIDED_RUNTIME_CSP = (
    "default-src 'none'; style-src 'unsafe-inline' 'self'; manifest-src 'self'; "
    "base-uri 'none'; form-action 'none'; script-src 'self'; connect-src 'self'"
)


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


def guided_source(body: str, *, csp: str = GUIDED_CSP) -> str:
    return (
        "<html><head>"
        f'<meta http-equiv="Content-Security-Policy" content="{csp}">'
        "</head><body><main>"
        + body
        + "</main></body></html>"
    )


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

    def test_guided_page_receives_same_origin_glossary_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "glossary-model.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            page = root / "guided" / "skill" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text(guided_source("Publication catalog"), encoding="utf-8")

            changed, links = annotate_site(root, glossary)

            self.assertEqual((changed, links), (1, 1))
            rendered = page.read_text(encoding="utf-8")
            self.assertIn(
                '<a class="glossary-term" href="/glossary/#templates-publication-catalog"',
                rendered,
            )
            self.assertIn(RUNTIME_STYLE, rendered)
            self.assertIn(RUNTIME_SCRIPT, rendered)
            self.assertIn(f'content="{GUIDED_RUNTIME_CSP}"', rendered)
            self.assertNotIn("connect-src *", rendered)
            self.assertNotIn("'unsafe-eval'", rendered)

    def test_guided_filename_stem_receives_same_runtime_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "glossary-model.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            page = root / "guided.html"
            page.write_text(guided_source("Publication catalog"), encoding="utf-8")

            changed, links = annotate_site(root, glossary)

            self.assertEqual((changed, links), (1, 1))
            rendered = page.read_text(encoding="utf-8")
            self.assertIn(RUNTIME_STYLE, rendered)
            self.assertIn(RUNTIME_SCRIPT, rendered)
            self.assertIn(f'content="{GUIDED_RUNTIME_CSP}"', rendered)

    def test_unannotated_guided_page_retains_original_csp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "glossary-model.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            page = root / "guided" / "skill" / "index.html"
            page.parent.mkdir(parents=True)
            original = guided_source("No matching vocabulary.")
            page.write_text(original, encoding="utf-8")

            changed, links = annotate_site(root, glossary)

            self.assertEqual((changed, links), (0, 0))
            self.assertEqual(page.read_text(encoding="utf-8"), original)

    def test_guided_runtime_preserves_stricter_same_origin_style_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "glossary-model.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            page = root / "guided" / "skill" / "index.html"
            page.parent.mkdir(parents=True)
            csp = "default-src 'none'; style-src 'self'; script-src 'self'"
            page.write_text(
                guided_source("Publication catalog", csp=csp),
                encoding="utf-8",
            )

            changed, links = annotate_site(root, glossary)

            self.assertEqual((changed, links), (1, 1))
            rendered = page.read_text(encoding="utf-8")
            self.assertIn(
                'content="default-src \'none\'; style-src \'self\'; script-src \'self\'; connect-src \'self\'"',
                rendered,
            )
            self.assertNotIn("style-src 'unsafe-inline'", rendered)

    def test_guided_runtime_rejects_broader_script_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "glossary-model.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            page = root / "guided" / "skill" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text(
                guided_source(
                    "Publication catalog",
                    csp=(
                        "default-src 'none'; style-src 'unsafe-inline'; "
                        "script-src 'self' 'unsafe-inline'"
                    ),
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                GlossaryAnnotationFinalizeError,
                "guided script-src must be exactly",
            ):
                annotate_site(root, glossary)

    def test_guided_runtime_rejects_broader_style_and_connect_policies(self) -> None:
        cases = (
            (
                "style",
                "default-src 'none'; style-src *; script-src 'self'",
                "guided style-src must remain limited",
            ),
            (
                "connect",
                "default-src 'none'; style-src 'unsafe-inline'; script-src 'self'; "
                "connect-src 'self' https://external.example",
                "guided connect-src must be exactly",
            ),
        )
        for name, csp, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                glossary = root / "glossary-model.json"
                glossary.write_text(json.dumps(model()), encoding="utf-8")
                page = root / "guided" / "skill" / "index.html"
                page.parent.mkdir(parents=True)
                page.write_text(
                    guided_source("Publication catalog", csp=csp),
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(GlossaryAnnotationFinalizeError, expected):
                    annotate_site(root, glossary)

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
            page = root / "guided" / "skill" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text(guided_source("Publication catalog"), encoding="utf-8")

            self.assertEqual(annotate_site(root, glossary), (1, 1))
            first = page.read_text(encoding="utf-8")
            self.assertEqual(annotate_site(root, glossary), (0, 0))
            second = page.read_text(encoding="utf-8")

            self.assertEqual(second, first)
            self.assertEqual(second.count(RUNTIME_STYLE), 1)
            self.assertEqual(second.count(RUNTIME_SCRIPT), 1)
            self.assertEqual(second.count("connect-src 'self'"), 1)

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
