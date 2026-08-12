from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.generate_index_navigation import generate_graph
from scripts import generate_index_navigation_viewer as viewer
from test_index_navigation_viewer_review_round_20260812 import make_fixture


class CurrentIndexNavigationViewerReviewRoundBTests(unittest.TestCase):
    def test_tampered_graph_content_must_match_locked_provider_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output = make_fixture(root)
            graph = generate_graph("TakashiSasaki/templates", providers)
            graph["providers"][0]["edges"][0]["label"] = "Substituted navigation"

            with self.assertRaisesRegex(
                viewer.IndexNavigationViewerError,
                "graph content does not match locked revision",
            ):
                viewer.generate_viewer(
                    "TakashiSasaki/templates", graph, site_root, output, providers
                )
            self.assertFalse((output / "guided").exists())

    def test_duplicate_heading_anchors_use_python_markdown_suffixes(self) -> None:
        self.assertEqual(
            viewer.heading_anchors(["Architecture", "Architecture", "Architecture"]),
            ["architecture", "architecture_1", "architecture_2"],
        )


if __name__ == "__main__":
    unittest.main()
