from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from scripts.finalize_glossary_annotations import (
    GlossaryAnnotationFinalizeError,
    annotate_html,
    annotate_site,
)
from scripts.glossary_annotation import GlossaryAnnotationError, build_annotation_index


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
                "localized_labels": {
                    "ja": {"term": "公開カタログ", "aliases": []}
                },
                "origin": "repository",
                "definition": "A provider-controlled publication declaration.",
                "provider": "site",
                "source_path": "docs/glossary.yml",
                "source_revision": REVISION,
            },
            {
                "id": "external-git-branch",
                "term": "Branch",
                "aliases": [],
                "origin": "external",
                "summary": "A named line of development.",
                "authority": {
                    "kind": "upstream",
                    "sources": [
                        {
                            "title": "Git glossary",
                            "url": "https://git-scm.com/docs/gitglossary",
                        }
                    ],
                },
                "provider": "site",
                "source_path": "docs/glossary.yml",
                "source_revision": REVISION,
            },
        ],
    }


class FinalizeGlossaryAnnotationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = build_annotation_index(model())

    def test_annotates_only_md_content_when_present(self) -> None:
        source = (
            '<html><body><main><p>Publication catalog outside.</p>'
            '<div class="md-content__inner"><p>Publication catalog inside.</p></div>'
            '</main></body></html>'
        )

        rendered, count = annotate_html(source, self.index)

        self.assertEqual(count, 1)
        self.assertIn("Publication catalog outside.", rendered)
        self.assertIn(
            'data-glossary-id="templates-publication-catalog">Publication catalog</a> inside.',
            rendered,
        )

    def test_duplicate_class_attributes_are_aggregated_for_content_detection(self) -> None:
        source = (
            '<html><body><div class="wrapper" class="md-content__inner">'
            '<p>Publication catalog</p></div></body></html>'
        )

        rendered, count = annotate_html(source, self.index)

        self.assertEqual(count, 1)
        self.assertIn('data-glossary-id="templates-publication-catalog"', rendered)

    def test_content_class_mentions_outside_attributes_do_not_disable_main_fallback(self) -> None:
        source = (
            '<html><body><!-- md-content__inner -->'
            '<main><p>Publication catalog</p>'
            '<script>const example = "md-content__inner";</script></main>'
            '</body></html>'
        )

        rendered, count = annotate_html(source, self.index)

        self.assertEqual(count, 1)
        self.assertIn('data-glossary-id="templates-publication-catalog"', rendered)
        self.assertIn('const example = "md-content__inner";', rendered)

    def test_generated_main_is_fallback_content_region(self) -> None:
        source = '<html><body><main><p>この公開カタログを確認する。</p></main></body></html>'

        rendered, count = annotate_html(source, self.index)

        self.assertEqual(count, 1)
        self.assertIn(
            'href="/glossary/#templates-publication-catalog" '
            'data-glossary-id="templates-publication-catalog">公開カタログ</a>',
            rendered,
        )

    def test_character_references_are_matched_as_decoded_text_and_reescaped(self) -> None:
        dynamic = model()
        terms = dynamic["terms"]
        assert isinstance(terms, list)
        terms.append(
            {
                "id": "templates-r-and-d",
                "term": "R&D",
                "aliases": [],
                "origin": "repository",
                "definition": "Research and development.",
                "provider": "site",
                "source_path": "docs/glossary.yml",
                "source_revision": REVISION,
            }
        )
        index = build_annotation_index(dynamic)

        for encoded in ("R&amp;D", "R&#38;D", "R&#x26;D"):
            with self.subTest(encoded=encoded):
                source = f"<main><p>{encoded} guidance</p></main>"
                rendered, count = annotate_html(source, index)
                self.assertEqual(count, 1)
                self.assertIn(
                    'data-glossary-id="templates-r-and-d">R&amp;D</a> guidance',
                    rendered,
                )

    def test_semicolonless_ampersand_text_keeps_visible_text_when_neighbor_is_annotated(self) -> None:
        source = "<main><p>AT&T Branch</p></main>"

        rendered, count = annotate_html(source, self.index)

        self.assertEqual(count, 1)
        self.assertIn("AT&amp;T ", rendered)
        self.assertNotIn("AT&amp;T;", rendered)
        self.assertIn(
            'data-glossary-id="external-git-branch">Branch</a>',
            rendered,
        )

    def test_code_links_navigation_and_specialized_containers_are_not_annotated(self) -> None:
        source = (
            '<main><nav>Branch</nav><p><code>Branch</code> Branch '
            '<a href="/x">Branch</a></p>'
            '<svg><text>Publication catalog</text></svg>'
            '<math><mtext>Publication catalog</mtext></math>'
            '<template><p>Publication catalog</p></template>'
            '<option>Publication catalog</option></main>'
        )

        rendered, count = annotate_html(source, self.index)

        self.assertEqual(count, 1)
        self.assertEqual(rendered.count('data-glossary-id="external-git-branch"'), 1)
        self.assertEqual(rendered.count('data-glossary-id='), 1)
        self.assertIn("<nav>Branch</nav>", rendered)
        self.assertIn("<code>Branch</code>", rendered)
        self.assertIn('<a href="/x">Branch</a>', rendered)
        self.assertIn("<text>Publication catalog</text>", rendered)
        self.assertIn("<mtext>Publication catalog</mtext>", rendered)
        self.assertIn("<template><p>Publication catalog</p></template>", rendered)
        self.assertIn("<option>Publication catalog</option>", rendered)

    def test_void_elements_do_not_corrupt_content_state(self) -> None:
        source = (
            '<html><head><meta charset="utf-8"><link rel="x" href="/x"></head>'
            '<body><main><p>Publication catalog<br> Branch</p>'
            '<img src="/x.png" alt="Branch"><p>Publication catalog</p></main></body></html>'
        )

        rendered, count = annotate_html(source, self.index)

        self.assertEqual(count, 3)
        self.assertEqual(
            rendered.count('data-glossary-id="templates-publication-catalog"'), 2
        )
        self.assertEqual(rendered.count('data-glossary-id="external-git-branch"'), 1)
        self.assertIn('<meta charset="utf-8">', rendered)
        self.assertIn('<img src="/x.png" alt="Branch">', rendered)

    def test_unmatched_end_tag_after_self_closing_nonvoid_does_not_pop_parent_state(self) -> None:
        source = (
            '<main><p>Before <span class="icon" /></span> Publication catalog</p>'
            '<p>Publication catalog</p></main>'
        )

        rendered, count = annotate_html(source, self.index)

        self.assertEqual(count, 2)
        self.assertEqual(
            rendered.count('data-glossary-id="templates-publication-catalog"'),
            2,
        )

    def test_existing_annotation_is_idempotent(self) -> None:
        source = '<main><p>Publication catalog.</p></main>'
        first, first_count = annotate_html(source, self.index)
        second, second_count = annotate_html(first, self.index)

        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 0)
        self.assertEqual(second, first)

    def test_site_finalizer_skips_non_document_viewer_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "index.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            normal = root / "guide" / "index.html"
            files = root / "files" / "site" / "content" / "x.html"
            glossary_page = root / "glossary" / "index.html"
            tree = root / "repository-trees" / "site" / "index.html"
            root_glossary = root / "glossary.html"
            root_files = root / "files.html"
            root_tree = root / "repository-trees.html"
            excluded = (files, glossary_page, tree, root_glossary, root_files, root_tree)
            for path in (normal, *excluded):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    '<html><body><main>Publication catalog</main></body></html>',
                    encoding="utf-8",
                )

            changed, links = annotate_site(root, glossary)

            self.assertEqual((changed, links), (1, 1))
            self.assertIn("data-glossary-id", normal.read_text(encoding="utf-8"))
            for path in excluded:
                self.assertNotIn("data-glossary-id", path.read_text(encoding="utf-8"))

    def test_annotation_index_errors_are_wrapped_at_finalizer_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "index.json"
            glossary.write_text(json.dumps(model()), encoding="utf-8")
            with patch(
                "scripts.finalize_glossary_annotations.build_annotation_index",
                side_effect=GlossaryAnnotationError("invalid annotation model"),
            ):
                with self.assertRaisesRegex(
                    GlossaryAnnotationFinalizeError,
                    "unable to prepare Glossary annotation data",
                ):
                    annotate_site(root, glossary)

    def test_ambiguous_label_warning_is_emitted_to_stderr(self) -> None:
        ambiguous_model = model()
        terms = ambiguous_model["terms"]
        assert isinstance(terms, list)
        first = terms[0]
        second = terms[1]
        assert isinstance(first, dict) and isinstance(second, dict)
        first["aliases"] = ["Shared label"]
        second["aliases"] = ["SHARED LABEL"]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary = root / "index.json"
            glossary.write_text(json.dumps(ambiguous_model), encoding="utf-8")
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                changed, links = annotate_site(root, glossary)

            self.assertEqual((changed, links), (0, 0))
            self.assertIn("skipped ambiguous labels: shared label", stderr.getvalue())

    def test_new_glossary_term_is_annotated_without_html_specific_configuration(self) -> None:
        dynamic = model()
        terms = dynamic["terms"]
        assert isinstance(terms, list)
        terms.append(
            {
                "id": "templates-future-term",
                "term": "Future term",
                "aliases": [],
                "origin": "repository",
                "definition": "Added later.",
                "provider": "site",
                "source_path": "docs/glossary.yml",
                "source_revision": REVISION,
            }
        )
        index = build_annotation_index(dynamic)

        rendered, count = annotate_html("<main>Future term</main>", index)

        self.assertEqual(count, 1)
        self.assertIn('data-glossary-id="templates-future-term"', rendered)


if __name__ == "__main__":
    unittest.main()
