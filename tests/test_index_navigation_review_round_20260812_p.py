import unittest
from urllib.parse import urlsplit

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


class LatestIndexNavigationReviewRoundPTests(unittest.TestCase):
    def test_incomplete_inline_link_syntax_remains_literal_text(self) -> None:
        for literal in ("[draft](", "[draft](unfinished"):
            with self.subTest(literal=literal):
                parsed = navigation.parse_index(
                    f"# Docs {literal}\n\n"
                    f"* [Overview](overview.md) - Notes {literal}\n",
                    "docs/index.md",
                )
                self.assertEqual(parsed.title, f"Docs {literal}")
                self.assertEqual(parsed.links[0].description, f"Notes {literal}")

        with self.assertRaisesRegex(IndexNavigationError, "unsupported inline link in heading"):
            navigation.parse_index(
                "# [Docs](overview.md)\n",
                "docs/index.md",
            )

    def test_invalid_unicode_payloads_in_ascii_alabels_are_rejected(self) -> None:
        for target in (
            "https://xn--a-wbb.com/",
            "https://xn--a-zhcd.com/",
        ):
            with self.subTest(target=target):
                with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
                    navigation.validate_external_location(
                        urlsplit(target),
                        "docs/index.md",
                        2,
                        target,
                    )

    def test_multiple_trailing_dots_do_not_create_ipv4_candidates(self) -> None:
        for target in (
            "https://example.999../",
            "https://4294967296../",
        ):
            with self.subTest(target=target):
                navigation.validate_external_location(
                    urlsplit(target),
                    "docs/index.md",
                    2,
                    target,
                )


if __name__ == "__main__":
    unittest.main()
