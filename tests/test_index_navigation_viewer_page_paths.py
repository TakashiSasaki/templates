from __future__ import annotations

import unittest

from scripts.generate_index_navigation_viewer import render_index_page, render_landing


class IndexNavigationViewerPagePathTests(unittest.TestCase):
    def test_index_page_displays_its_public_path_before_page_content(self) -> None:
        index = {
            "path": "docs/reference/index.md",
            "title": "Reference",
            "sections": [],
            "depth": 1,
            "object_id": "b" * 40,
        }
        provider = {
            "name": "skill",
            "revision": "a" * 40,
            "root_index": "docs/index.md",
            "indexes": [
                {
                    "path": "docs/index.md",
                    "title": "Docs",
                    "sections": [],
                    "depth": 0,
                    "object_id": "c" * 40,
                },
                index,
            ],
            "edges": [
                {
                    "source": "docs/index.md",
                    "section": None,
                    "label": "Reference",
                    "description": "Reference documents.",
                    "line": 3,
                    "raw_target": "reference/index.md",
                    "kind": "index",
                    "target": "docs/reference/index.md",
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

        expected = (
            '<p class="page-path"><span class="page-path-label">Page path:</span> '
            '<code>/guided/skill/docs/reference/</code></p>'
        )
        self.assertIn(expected, rendered)
        self.assertLess(rendered.index(expected), rendered.index("Index-guided navigation"))
        self.assertIn("<strong>Source:</strong> <code>docs/reference/index.md</code>", rendered)

    def test_guided_landing_displays_its_public_path(self) -> None:
        graph = {
            "providers": [
                {
                    "name": "skill",
                    "revision": "a" * 40,
                    "diagnostics": {
                        "index_count": 1,
                        "edge_count": 0,
                        "max_index_depth": 0,
                    },
                }
            ]
        }

        rendered = render_landing(graph)

        self.assertIn(
            '<p class="page-path"><span class="page-path-label">Page path:</span> '
            '<code>/guided/</code></p>',
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
