from __future__ import annotations

import unittest

from scripts.generate_index_navigation_viewer import render_index_page


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


if __name__ == "__main__":
    unittest.main()
