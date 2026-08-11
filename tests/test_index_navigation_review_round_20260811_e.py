from __future__ import annotations

import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


class LatestIndexNavigationReviewRoundETests(unittest.TestCase):
    def test_unescaped_emphasis_markers_fail_closed_in_headings(self) -> None:
        for heading in ("*API*", "_API_", "**API**", "__API__"):
            with self.subTest(heading=heading):
                with self.assertRaisesRegex(
                    IndexNavigationError,
                    "unsupported emphasis in heading",
                ):
                    navigation.parse_index(
                        f"# Docs\n\n## {heading}\n",
                        "docs/index.md",
                    )

    def test_unescaped_emphasis_markers_fail_closed_in_link_labels(self) -> None:
        for label in ("Guide *advanced*", "Guide _advanced_"):
            with self.subTest(label=label):
                with self.assertRaisesRegex(
                    IndexNavigationError,
                    "unsupported emphasis in link label",
                ):
                    navigation.parse_index(
                        f"# Docs\n\n* [{label}](overview.md) - Read it.\n",
                        "docs/index.md",
                    )

    def test_escaped_emphasis_markers_remain_literal_text(self) -> None:
        parsed = navigation.parse_index(
            "# Escaped \\*API\\*\n\n"
            "* [Guide \\_advanced\\_](overview.md) - Read it.\n",
            "docs/index.md",
        )

        self.assertEqual(parsed.title, "Escaped *API*")
        self.assertEqual(parsed.links[0].label, "Guide _advanced_")

    def test_pointy_destination_scans_through_separator_like_text(self) -> None:
        parsed = navigation.parse_index(
            "# Docs\n\n* [Odd](<foo) - x>) - Read it.\n",
            "docs/index.md",
        )

        self.assertEqual(parsed.links[0].raw_target, "<foo) - x>")
        self.assertEqual(parsed.links[0].description, "Read it.")

        resolved = navigation.resolve_link(
            "docs/index.md",
            parsed.links[0],
            {
                "docs/index.md": ("blob", "100644", "a" * 40),
                "docs/foo) - x": ("blob", "100644", "b" * 40),
            },
        )
        self.assertEqual(
            resolved,
            {"kind": "file", "target": "docs/foo) - x", "fragment": None},
        )

    def test_bare_destination_scanner_preserves_balanced_parentheses(self) -> None:
        parsed = navigation.parse_index(
            "# Docs\n\n* [API](spec_(v1).md) - Read it.\n",
            "docs/index.md",
        )

        self.assertEqual(parsed.links[0].raw_target, "spec_(v1).md")
        self.assertEqual(parsed.links[0].description, "Read it.")


if __name__ == "__main__":
    unittest.main()
