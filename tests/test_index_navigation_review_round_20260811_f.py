import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError, ParsedLink


class LatestIndexNavigationReviewRoundFTests(unittest.TestCase):
    def test_leading_columns_affect_list_tab_expansion(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "list marker indentation"):
            navigation.parse_index(
                "# Docs\n\n  * \t[Overview](overview.md) - Read it.\n",
                "docs/index.md",
            )

        parsed = navigation.parse_index(
            "# Docs\n\n  * [Overview](overview.md) - Read it.\n",
            "docs/index.md",
        )
        self.assertEqual(parsed.links[0].label, "Overview")

    def test_heading_inline_link_is_rejected(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "unsupported inline link in heading"):
            navigation.parse_index(
                "# Docs\n\n## [API](spec.md)\n",
                "docs/index.md",
            )

    def test_description_entities_follow_rendered_text(self) -> None:
        parsed = navigation.parse_index(
            "# Docs\n\n* [Overview](overview.md) - Fish &amp; Chips.\n",
            "docs/index.md",
        )
        self.assertEqual(parsed.links[0].description, "Fish & Chips.")

    def test_description_inline_link_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            IndexNavigationError,
            "unsupported inline link in link description",
        ):
            navigation.parse_index(
                "# Docs\n\n* [Overview](overview.md) - See [details](details.md).\n",
                "docs/index.md",
            )

    def test_external_literal_backslash_is_percent_encoded(self) -> None:
        link = ParsedLink(
            label="External",
            raw_target=r"https://example.com/a\file",
            description="Read it.",
            section=None,
            line=3,
        )

        resolved = navigation.resolve_link("docs/index.md", link, {})

        self.assertEqual(
            resolved,
            {
                "kind": "external",
                "target": "https://example.com/a%5Cfile",
                "fragment": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
