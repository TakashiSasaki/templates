from __future__ import annotations

import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError, ParsedLink


class FollowupIndexNavigationReviewTests(unittest.TestCase):
    def test_c1_controls_are_rejected_in_text_paths_and_fragments(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "disallowed control"):
            navigation.decode_index_text(b"# Docs\n\xc2\x9b\n", "docs/index.md")
        with self.assertRaisesRegex(IndexNavigationError, "disallowed control"):
            navigation.decode_link_path("overview%C2%9B.md", "docs/index.md", 2)
        with self.assertRaisesRegex(IndexNavigationError, "disallowed control"):
            navigation.decode_fragment("%C2%9B", "docs/index.md", 2)

    def test_raw_link_controls_are_rejected_before_url_parsing(self) -> None:
        link = ParsedLink(
            label="Overview",
            raw_target="over\tview.md",
            description="Read it.",
            section=None,
            line=2,
        )
        entries = {"docs/overview.md": ("blob", "100644", "a" * 40)}
        with self.assertRaisesRegex(
            IndexNavigationError,
            "invalid whitespace or controls",
        ):
            navigation.resolve_link("docs/index.md", link, entries)

    def test_empty_same_document_fragment_is_preserved(self) -> None:
        link = ParsedLink(
            label="Top",
            raw_target="#",
            description="Return to the top.",
            section=None,
            line=2,
        )
        resolved = navigation.resolve_link("docs/index.md", link, {})
        self.assertEqual(
            resolved,
            {"kind": "fragment", "target": "docs/index.md", "fragment": ""},
        )

    def test_provider_path_must_not_be_empty(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "path must not be empty"):
            navigation.parse_providers(
                ["skill=", "policy=policy", "webapp=webapp"]
            )

    def test_non_ascii_leading_whitespace_is_not_trimmed_into_structure(self) -> None:
        for content in (
            "# Docs\n\n\u00a0## Not a heading\n",
            "# Docs\n\n\u2003* [Overview](overview.md) - Not a link.\n",
        ):
            with self.subTest(content=content):
                with self.assertRaisesRegex(IndexNavigationError, "unsupported index.md content"):
                    navigation.parse_index(content, "docs/index.md")

    def test_link_label_must_not_trim_to_empty(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "link label is empty"):
            navigation.parse_index(
                "# Docs\n\n* [ ](overview.md) - Read it.\n",
                "docs/index.md",
            )


if __name__ == "__main__":
    unittest.main()
