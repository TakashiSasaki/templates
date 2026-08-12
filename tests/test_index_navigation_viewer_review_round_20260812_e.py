from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.generate_index_navigation import generate_graph
from scripts import generate_index_navigation_viewer as viewer
from test_index_navigation_viewer_review_round_20260812 import make_fixture


class LatestIndexNavigationViewerReviewRoundETests(unittest.TestCase):
    def test_keyboard_interrupt_removes_new_guided_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output = make_fixture(root)
            graph = generate_graph("TakashiSasaki/templates", providers)
            original_write_text = Path.write_text

            def interrupting_write_text(path: Path, data: str, *args, **kwargs):
                if path == output / "guided/graph.json":
                    raise KeyboardInterrupt()
                return original_write_text(path, data, *args, **kwargs)

            with mock.patch.object(Path, "write_text", new=interrupting_write_text):
                with self.assertRaises(KeyboardInterrupt):
                    viewer.generate_viewer(
                        "TakashiSasaki/templates", graph, site_root, output, providers
                    )

            self.assertFalse((output / "guided").exists())


if __name__ == "__main__":
    unittest.main()
