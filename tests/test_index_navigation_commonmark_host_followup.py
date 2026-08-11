from __future__ import annotations

import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError, ParsedLink


REGULAR_BLOB = ("blob", "100644", "0" * 40)


def link(target: str) -> ParsedLink:
    return ParsedLink(
        label="Target",
        raw_target=target,
        description="Follow it.",
        section=None,
        line=3,
    )


class CommonMarkAndHostFollowupTests(unittest.TestCase):
    def test_hash_only_atx_content_is_an_empty_heading(self) -> None:
        for content in ("# #\n", "# ###\n", "### ###\n"):
            with self.subTest(content=content), self.assertRaisesRegex(
                IndexNavigationError,
                "empty heading",
            ):
                navigation.parse_index(content, "docs/index.md")

    def test_escaped_link_label_terminator_is_not_navigation(self) -> None:
        with self.assertRaisesRegex(
            IndexNavigationError,
            "escaped link-label terminator",
        ):
            navigation.parse_index(
                "# Docs\n\n* [Guide\\](overview.md) - Read it.\n",
                "docs/index.md",
            )

    def test_whatwg_domain_allows_non_dns_ascii_code_points(self) -> None:
        for target in (
            "https://foo_bar.internal/path",
            "https://foo~bar.internal/path",
        ):
            with self.subTest(target=target):
                resolved = navigation.resolve_link("docs/index.md", link(target), {})
                self.assertEqual(resolved["kind"], "external")
                self.assertEqual(resolved["target"], target)

    def test_character_reference_can_decode_to_space_in_bare_destination(self) -> None:
        resolved = navigation.resolve_link(
            "docs/index.md",
            link("my&#32;file.md"),
            {"docs/my file.md": REGULAR_BLOB},
        )
        self.assertEqual(resolved["kind"], "file")
        self.assertEqual(resolved["target"], "docs/my file.md")

    def test_backslash_escaped_ampersand_does_not_expose_character_reference(self) -> None:
        entries = {
            "docs/overview&period;md": REGULAR_BLOB,
            "docs/overview.md": REGULAR_BLOB,
        }

        escaped = navigation.resolve_link(
            "docs/index.md",
            link(r"overview\&period;md"),
            entries,
        )
        entity = navigation.resolve_link(
            "docs/index.md",
            link("overview&period;md"),
            entries,
        )

        self.assertEqual(escaped["target"], "docs/overview&period;md")
        self.assertEqual(entity["target"], "docs/overview.md")


if __name__ == "__main__":
    unittest.main()
