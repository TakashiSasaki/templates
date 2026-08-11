from __future__ import annotations

import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError, ParsedLink


class LatestIndexNavigationReviewRoundTests(unittest.TestCase):
    def test_repository_root_without_index_remains_directory(self) -> None:
        link = ParsedLink(
            label="Repository root",
            raw_target="../",
            description="Browse the repository root.",
            section=None,
            line=3,
        )
        entries = {
            "docs/index.md": ("blob", "100644", "a" * 40),
            "README.md": ("blob", "100644", "b" * 40),
        }

        resolved = navigation.resolve_link("docs/index.md", link, entries)

        self.assertEqual(
            resolved,
            {"kind": "directory", "target": ".", "fragment": None},
        )

    def test_empty_fragment_is_preserved_for_nonempty_targets(self) -> None:
        entries = {
            "docs/index.md": ("blob", "100644", "a" * 40),
            "docs/overview.md": ("blob", "100644", "b" * 40),
        }
        file_link = ParsedLink(
            label="Overview",
            raw_target="overview.md#",
            description="Explicit empty fragment.",
            section=None,
            line=3,
        )
        external_link = ParsedLink(
            label="External",
            raw_target="https://example.com/#",
            description="Explicit empty fragment.",
            section=None,
            line=4,
        )

        file_edge = navigation.resolve_link("docs/index.md", file_link, entries)
        external_edge = navigation.resolve_link("docs/index.md", external_link, entries)

        self.assertEqual(file_edge["fragment"], "")
        self.assertEqual(external_edge["fragment"], "")

    def test_named_character_reference_requires_exact_html5_name(self) -> None:
        self.assertEqual(
            navigation.decode_markdown_destination(
                "overview&copyx;.md", "docs/index.md", 3
            ),
            "overview&copyx;.md",
        )
        self.assertEqual(
            navigation.decode_markdown_destination(
                "overview&copy;.md", "docs/index.md", 3
            ),
            "overview©.md",
        )

    def test_escaped_destination_closing_parenthesis_is_not_a_terminator(self) -> None:
        with self.assertRaisesRegex(
            IndexNavigationError,
            "escaped link-destination terminator|unsupported index.md content",
        ):
            navigation.parse_index(
                "# Docs\n\n* [Foo](overview.md\\) - Read it.\n",
                "docs/index.md",
            )

    def test_list_marker_spacing_is_limited_to_four_columns(self) -> None:
        for spacing in (" ", "  ", "   ", "    ", "\t"):
            with self.subTest(spacing=repr(spacing)):
                parsed = navigation.parse_index(
                    f"# Docs\n\n*{spacing}[Overview](overview.md) - Read it.\n",
                    "docs/index.md",
                )
                self.assertEqual(parsed.links[0].label, "Overview")

        with self.assertRaisesRegex(
            IndexNavigationError,
            "list marker indentation|unsupported index.md content",
        ):
            navigation.parse_index(
                "# Docs\n\n*     [Overview](overview.md) - Read it.\n",
                "docs/index.md",
            )


if __name__ == "__main__":
    unittest.main()
