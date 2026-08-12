from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import generate_index_navigation as navigation
from scripts.generate_repository_trees import RepositoryTreeError


class IndexNavigationInputBoundaryTests(unittest.TestCase):
    def test_index_text_rejects_nul_invalid_utf8_and_bidi_controls(self) -> None:
        for content, expected in (
            (b"# Root\0\n", "NUL byte"),
            (b"# Root\xff\n", "strict UTF-8"),
            ("# Root\u202e\n".encode(), "disallowed control character"),
        ):
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(navigation.IndexNavigationError, expected):
                    navigation.decode_index_text(content, "docs/index.md")

    def test_atx_headings_accept_one_to_three_leading_ascii_spaces(self) -> None:
        for spaces in (1, 2, 3):
            with self.subTest(spaces=spaces):
                parsed = navigation.parse_index(
                    " " * spaces + "# Root\n\n* [Guide](guide.md) - Read it.\n",
                    "docs/index.md",
                )
                self.assertEqual(parsed.title, "Root")

    def test_index_shape_rejects_multiple_titles_and_links_before_title(self) -> None:
        for text, expected in (
            (
                "# One\n\n# Two\n",
                "multiple level-1 headings",
            ),
            (
                "* [Guide](guide.md) - Read it.\n\n# Root\n",
                "link precedes title",
            ),
        ):
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(navigation.IndexNavigationError, expected):
                    navigation.parse_index(text, "docs/index.md")

    def test_cli_formats_graph_and_tree_failures_as_parser_errors(self) -> None:
        argv = [
            "generate_index_navigation.py",
            "--repository",
            "TakashiSasaki/templates",
            "--output",
            str(Path("out.json")),
            "--provider",
            "skill=skill",
            "--provider",
            "policy=policy",
            "--provider",
            "webapp=webapp",
        ]
        for error in (
            navigation.IndexNavigationError("graph generation failed"),
            RepositoryTreeError("tree inspection failed"),
        ):
            with self.subTest(error=type(error).__name__):
                stderr = io.StringIO()
                with mock.patch.object(sys, "argv", argv), mock.patch.object(
                    navigation._base,
                    "generate_graph",
                    side_effect=error,
                ), mock.patch.object(sys, "stderr", stderr):
                    with self.assertRaises(SystemExit) as raised:
                        navigation.main()
                self.assertEqual(raised.exception.code, 2)
                self.assertIn(str(error), stderr.getvalue())

    def test_write_graph_formats_os_errors_as_navigation_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with self.assertRaisesRegex(
                navigation.IndexNavigationError,
                "unable to write navigation graph output",
            ):
                navigation.write_graph(output, {"schema_version": 1})


if __name__ == "__main__":
    unittest.main()
