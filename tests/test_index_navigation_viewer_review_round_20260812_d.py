from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.generate_index_navigation import generate_graph
from scripts import generate_index_navigation_viewer as viewer
from test_index_navigation_viewer_review_round_20260812 import make_fixture


class CountingEdge(dict):
    section_gets = 0

    def get(self, key, default=None):
        if key == "section":
            type(self).section_gets += 1
        return super().get(key, default)


class CurrentIndexNavigationViewerReviewRoundDTests(unittest.TestCase):
    def test_existing_guided_destination_is_never_removed_on_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output = make_fixture(root)
            graph = generate_graph("TakashiSasaki/templates", providers)
            guided = output / "guided"
            guided.mkdir()
            sentinel = guided / "keep.txt"
            sentinel.write_text("preserve me\n", encoding="utf-8")

            with self.assertRaisesRegex(
                viewer.IndexNavigationViewerError,
                "destination already exists",
            ):
                viewer.generate_viewer(
                    "TakashiSasaki/templates", graph, site_root, output, providers
                )

            self.assertTrue(guided.is_dir())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve me\n")

    def test_heading_anchor_normalizes_decomposed_unicode(self) -> None:
        self.assertEqual(viewer.heading_anchor("Cafe\u0301"), "café")

    def test_section_edge_partition_is_linear_in_source_edges(self) -> None:
        section_count = 80
        index = {
            "path": "docs/index.md",
            "title": "Docs",
            "sections": [
                {"title": f"Section {number}", "level": 2}
                for number in range(section_count)
            ],
            "depth": 0,
            "object_id": "a" * 40,
        }
        edges = [
            CountingEdge(
                source="docs/index.md",
                section=f"Section {number}",
                label=f"Link {number}",
                description="Read it.",
                line=number + 2,
                raw_target="https://example.com/",
                kind="external",
                target="https://example.com/",
                fragment=None,
            )
            for number in range(section_count)
        ]
        provider = {
            "name": "skill",
            "revision": "b" * 40,
            "root_index": "docs/index.md",
            "indexes": [index],
            "edges": edges,
            "diagnostics": {},
        }
        CountingEdge.section_gets = 0

        viewer.render_index_page(
            "TakashiSasaki/templates",
            provider,
            index,
            {},
            edges,
            {"docs/index.md": index},
            {},
        )

        self.assertLessEqual(CountingEdge.section_gets, section_count * 2)


if __name__ == "__main__":
    unittest.main()
