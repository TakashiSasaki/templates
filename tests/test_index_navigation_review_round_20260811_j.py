import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError, ParsedLink


class LatestIndexNavigationReviewRoundJTests(unittest.TestCase):
    def test_external_userinfo_entity_space_is_percent_encoded(self) -> None:
        link = ParsedLink(
            label="External",
            raw_target="https://user&#32;name@example.com/",
            description="Read it.",
            section=None,
            line=3,
        )

        resolved = navigation.resolve_link("docs/index.md", link, {})

        self.assertEqual(resolved["target"], "https://user%20name@example.com/")

    def test_external_pointy_userinfo_space_is_percent_encoded(self) -> None:
        link = ParsedLink(
            label="External",
            raw_target="<https://user name@example.com/>",
            description="Read it.",
            section=None,
            line=3,
        )

        resolved = navigation.resolve_link("docs/index.md", link, {})

        self.assertEqual(resolved["target"], "https://user%20name@example.com/")

    def test_pointy_destination_title_requires_separator_whitespace(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "unsupported index.md content"):
            navigation.parse_index(
                '# Docs\n\n* [Overview](<overview.md>"Title") - Read it.\n',
                "docs/index.md",
            )

    def test_pointy_destination_title_with_space_remains_valid(self) -> None:
        parsed = navigation.parse_index(
            '# Docs\n\n* [Overview](<overview.md> "Title") - Read it.\n',
            "docs/index.md",
        )

        self.assertEqual(parsed.links[0].raw_target, "<overview.md>")


if __name__ == "__main__":
    unittest.main()
