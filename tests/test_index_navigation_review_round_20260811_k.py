import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


class LatestIndexNavigationReviewRoundKTests(unittest.TestCase):
    def test_empty_inline_destination_resolves_same_document(self) -> None:
        parsed = navigation.parse_index(
            "# Docs\n\n* [Top]() - Return to the top.\n",
            "docs/index.md",
        )

        self.assertEqual(parsed.links[0].raw_target, "")
        self.assertEqual(
            navigation.resolve_link("docs/index.md", parsed.links[0], {}),
            {
                "kind": "fragment",
                "target": "docs/index.md",
                "fragment": None,
            },
        )

    def test_unassigned_unicode_host_fails_uts46_processing(self) -> None:
        link = navigation.ParsedLink(
            label="External",
            raw_target="https://a\u0378b.com/",
            description="Read it.",
            section=None,
            line=3,
        )

        with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
            navigation.resolve_link("docs/index.md", link, {})

    def test_lowercase_ascii_html_declaration_remains_raw_html(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "unsupported raw HTML in heading"):
            navigation.parse_index(
                "# Docs\n\n## API <!foo>\n",
                "docs/index.md",
            )

    def test_non_ascii_declaration_opener_remains_plain_text(self) -> None:
        parsed = navigation.parse_index(
            "# Docs\n\n## API <!é>\n",
            "docs/index.md",
        )

        self.assertEqual(parsed.sections[0].title, "API <!é>")

    def test_plus_bullet_remains_outside_reserved_index_shape(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "unsupported index.md content"):
            navigation.parse_index(
                "# Docs\n\n+ [Overview](overview.md) - Read it.\n",
                "docs/index.md",
            )


if __name__ == "__main__":
    unittest.main()
