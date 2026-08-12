import unittest
from urllib.parse import urlsplit

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


class LatestIndexNavigationReviewRoundOTests(unittest.TestCase):
    def test_short_commonmark_html_comment_forms_are_raw_html(self) -> None:
        for comment in ("<!-->", "<!--->"):
            with self.subTest(comment=comment):
                self.assertTrue(navigation.contains_commonmark_raw_html(comment))
                with self.assertRaisesRegex(IndexNavigationError, "unsupported raw HTML in heading"):
                    navigation.parse_index(
                        f"# Docs {comment}\n",
                        "docs/index.md",
                    )

    def test_unmatched_closing_link_syntax_remains_literal_text(self) -> None:
        parsed = navigation.parse_index(
            "# Literal ]( heading\n\n"
            "* [Overview](overview.md) - Literal ]( description.\n",
            "docs/index.md",
        )
        self.assertEqual(parsed.title, "Literal ]( heading")
        self.assertEqual(parsed.links[0].description, "Literal ]( description.")

        with self.assertRaisesRegex(IndexNavigationError, "unsupported inline link in heading"):
            navigation.parse_index(
                "# [Docs](overview.md)\n",
                "docs/index.md",
            )

    def test_contextually_valid_joiner_domains_are_accepted(self) -> None:
        for target in (
            "https://نامه‌ای.com/",
            "https://xn--mgba3gch31f060k.com/",
        ):
            with self.subTest(target=target):
                navigation.validate_external_location(
                    urlsplit(target),
                    "docs/index.md",
                    2,
                    target,
                )

    def test_character_reference_controls_are_checked_before_field_trimming(self) -> None:
        cases = (
            (
                "# &#9;Docs\n",
                "heading contains a disallowed control character",
            ),
            (
                "# Docs\n\n* [&#9;API](overview.md) - Read it.\n",
                "link label contains a disallowed control character",
            ),
            (
                "# Docs\n\n* [Overview](overview.md) - &#9;Read it.\n",
                "link description contains a disallowed control character",
            ),
        )
        for source, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(IndexNavigationError, message):
                    navigation.parse_index(source, "docs/index.md")


if __name__ == "__main__":
    unittest.main()
