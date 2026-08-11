from __future__ import annotations

import unittest

from scripts.generate_index_navigation_viewer import (
    IndexNavigationViewerError,
    edge_href,
    heading_anchor,
    index_page_path,
    page_shell,
    render_index_page,
    render_landing,
    validate_provider_graph,
    validate_repository_path,
)


def minimal_provider(**overrides: object) -> dict[str, object]:
    provider: dict[str, object] = {
        "name": "skill",
        "revision": "a" * 40,
        "root_index": "docs/index.md",
        "indexes": [
            {
                "path": "docs/index.md",
                "title": "Docs",
                "sections": [],
                "depth": 0,
                "object_id": "b" * 40,
            }
        ],
        "edges": [],
        "diagnostics": {
            "index_count": 1,
            "edge_count": 0,
            "max_index_depth": 0,
        },
    }
    provider.update(overrides)
    return provider


class IndexNavigationViewerHeadingEdgeTests(unittest.TestCase):
    def test_title_section_anchor_collision_is_disambiguated(self) -> None:
        index = {
            "path": "docs/index.md",
            "title": "Architecture",
            "sections": ["Architecture", "Links"],
            "depth": 0,
            "object_id": "b" * 40,
        }
        provider = {
            "name": "skill",
            "revision": "a" * 40,
            "root_index": "docs/index.md",
            "indexes": [index],
            "edges": [
                {
                    "source": "docs/index.md",
                    "section": None,
                    "label": "Second Architecture heading",
                    "description": "Jump to the disambiguated section anchor.",
                    "line": 3,
                    "raw_target": "#architecture-1",
                    "kind": "fragment",
                    "target": "docs/index.md",
                    "fragment": "architecture-1",
                }
            ],
            "diagnostics": {},
        }

        rendered = render_index_page(
            "TakashiSasaki/templates",
            provider,
            index,
            {},
        )

        self.assertIn('<h1 id="architecture">Architecture</h1>', rendered)
        self.assertIn('<h2 id="architecture-1">Architecture</h2>', rendered)
        self.assertIn('<h2 id="links">Links</h2>', rendered)
        self.assertIn('href="#architecture-1"', rendered)

    def test_unsectioned_links_do_not_invent_a_provider_h2(self) -> None:
        index = {
            "path": "docs/index.md",
            "title": "Docs",
            "sections": ["Links"],
            "depth": 0,
            "object_id": "b" * 40,
        }
        provider = {
            "name": "skill",
            "revision": "a" * 40,
            "root_index": "docs/index.md",
            "indexes": [index],
            "edges": [
                {
                    "source": "docs/index.md",
                    "section": None,
                    "label": "Specification",
                    "description": "An unsectioned external link.",
                    "line": 3,
                    "raw_target": "https://example.com/spec",
                    "kind": "external",
                    "target": "https://example.com/spec",
                    "fragment": None,
                }
            ],
            "diagnostics": {},
        }

        rendered = render_index_page(
            "TakashiSasaki/templates",
            provider,
            index,
            {},
        )

        self.assertEqual(rendered.count("<h2"), 1)
        self.assertIn('<h2 id="links">Links</h2>', rendered)
        self.assertNotIn("<h2>Links</h2>", rendered)
        self.assertIn("Links before the first provider section", rendered)

    def test_directory_edges_route_to_the_immutable_branch_browser(self) -> None:
        href, route_kind, external = edge_href(
            "skill",
            "a" * 40,
            {
                "kind": "directory",
                "target": "docs/examples",
                "fragment": None,
            },
            {},
        )

        self.assertEqual(href, "/files/skill/")
        self.assertEqual(route_kind, "repository directory")
        self.assertFalse(external)

    def test_non_index_source_path_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            IndexNavigationViewerError,
            "not an index source path",
        ):
            index_page_path("skill", "docs/overview.md")

    def test_source_file_line_fragment_uses_immutable_source(self) -> None:
        href, route_kind, external = edge_href(
            "skill",
            "a" * 40,
            {
                "kind": "file",
                "target": "docs/notes.md",
                "fragment": "L20",
            },
            {},
            "TakashiSasaki/templates",
        )

        self.assertEqual(
            href,
            "https://github.com/TakashiSasaki/templates/blob/"
            + ("a" * 40)
            + "/docs/notes.md#L20",
        )
        self.assertEqual(route_kind, "immutable source")
        self.assertTrue(external)

    def test_source_file_semantic_fragment_uses_immutable_source(self) -> None:
        href, route_kind, external = edge_href(
            "skill",
            "a" * 40,
            {
                "kind": "file",
                "target": "docs/notes.md",
                "fragment": "usage",
            },
            {},
            "TakashiSasaki/templates",
        )

        self.assertEqual(
            href,
            "https://github.com/TakashiSasaki/templates/blob/"
            + ("a" * 40)
            + "/docs/notes.md#usage",
        )
        self.assertEqual(route_kind, "immutable source")
        self.assertTrue(external)

    def test_guided_csp_allows_same_origin_manifest(self) -> None:
        rendered = page_shell("Docs", "<h1>Docs</h1>")
        self.assertIn("manifest-src 'self'", rendered)
        self.assertIn("default-src 'none'", rendered)

    def test_symbol_only_heading_cannot_produce_an_anchor(self) -> None:
        with self.assertRaisesRegex(
            IndexNavigationViewerError,
            "heading cannot produce a stable anchor",
        ):
            heading_anchor("!!!")

    def test_unicode_heading_anchor_uses_lower_not_casefold(self) -> None:
        self.assertEqual(heading_anchor("Straße"), "straße")

    def test_repository_colons_are_not_treated_as_traversal(self) -> None:
        validate_repository_path("docs/spec:v2.md", "file path")

    def test_provider_revision_and_object_ids_require_lowercase_full_shas(self) -> None:
        for revision in ("A" * 40, "z" * 40, "a" * 39):
            with self.subTest(revision=revision):
                with self.assertRaisesRegex(IndexNavigationViewerError, "revision is invalid"):
                    validate_provider_graph(minimal_provider(revision=revision))

        provider = minimal_provider()
        provider["indexes"][0]["object_id"] = "B" * 40
        with self.assertRaisesRegex(IndexNavigationViewerError, "index record is invalid"):
            validate_provider_graph(provider)

    def test_landing_escapes_untrusted_diagnostic_values(self) -> None:
        graph = {
            "providers": [
                minimal_provider(
                    diagnostics={
                        "index_count": "<script>alert(1)</script>",
                        "edge_count": "<b>2</b>",
                        "max_index_depth": "<img src=x>",
                    }
                )
            ]
        }

        rendered = render_landing(graph)

        self.assertNotIn("<script>alert(1)</script>", rendered)
        self.assertNotIn("<b>2</b>", rendered)
        self.assertNotIn("<img src=x>", rendered)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered)
        self.assertIn("&lt;b&gt;2&lt;/b&gt;", rendered)
        self.assertIn("&lt;img src=x&gt;", rendered)


if __name__ == "__main__":
    unittest.main()
