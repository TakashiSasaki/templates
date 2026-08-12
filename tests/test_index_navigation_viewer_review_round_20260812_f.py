import io
import sys
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from scripts import generate_index_navigation_viewer as viewer


class LatestIndexNavigationViewerReviewRoundFTests(unittest.TestCase):
    def test_cli_converts_output_oserror_to_argparse_error(self) -> None:
        stderr = io.StringIO()
        argv = [
            "generate_index_navigation_viewer.py",
            "--repository",
            "TakashiSasaki/templates",
            "--graph",
            "graph.json",
            "--site-root",
            "site",
            "--output-root",
            "output",
        ]
        with (
            patch.object(sys, "argv", argv),
            patch.object(viewer, "parse_providers", return_value={}),
            patch.object(viewer, "load_graph", return_value={}),
            patch.object(viewer, "generate_viewer", side_effect=OSError("disk full")),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as caught,
        ):
            viewer.main()

        self.assertEqual(caught.exception.code, 2)
        self.assertIn("disk full", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
