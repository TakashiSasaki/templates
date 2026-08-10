from __future__ import annotations

import unittest

from scripts.generate_index_navigation_viewer import (
    IndexNavigationViewerError,
    edge_href,
    index_page_path,
    page_shell,
    render_index_page,
)


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

    def test_source_file_line_fragment_stays_on_local_file_viewer(self) -> None:
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

        self.assertTrue(href.startswith("/files/skill/content/"))
        self.assertTrue(href.endswith("#L20"))
        self.assertEqual(route_kind, "source file")
        self.assertFalse(external)

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


if __name__ == "__main__":
    unittest.main()
