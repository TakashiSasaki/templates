import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError, ParsedLink


class LatestIndexNavigationReviewRoundHTests(unittest.TestCase):
    def test_bracketed_non_ipv6_external_host_is_rejected(self) -> None:
        malformed = ParsedLink(
            label="External",
            raw_target="https://[v1.foo]/",
            description="Read it.",
            section=None,
            line=3,
        )
        valid_ipv6 = ParsedLink(
            label="External",
            raw_target="https://[::1]/",
            description="Read it.",
            section=None,
            line=4,
        )

        with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
            navigation.resolve_link("docs/index.md", malformed, {})
        self.assertEqual(
            navigation.resolve_link("docs/index.md", valid_ipv6, {})["target"],
            "https://[::1]/",
        )

    def test_uri_autolink_inside_navigation_label_is_rejected(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "autolink in link label"):
            navigation.parse_index(
                "# Docs\n\n* [Guide <https://example.com>](overview.md) - Read it.\n",
                "docs/index.md",
            )

    def test_email_autolink_inside_navigation_label_is_rejected(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "autolink in link label"):
            navigation.parse_index(
                "# Docs\n\n* [Mail <docs@example.com>](overview.md) - Read it.\n",
                "docs/index.md",
            )

    def test_escaped_autolink_opener_remains_plain_label_text(self) -> None:
        parsed = navigation.parse_index(
            "# Docs\n\n* [Guide \\<https://example.com>](overview.md) - Read it.\n",
            "docs/index.md",
        )
        self.assertEqual(parsed.links[0].label, "Guide <https://example.com>")

    def test_raw_html_in_heading_is_rejected(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "raw HTML in heading"):
            navigation.parse_index(
                "# Docs\n\n## API <span>v2</span>\n",
                "docs/index.md",
            )

    def test_raw_html_comment_in_heading_is_rejected(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "raw HTML in heading"):
            navigation.parse_index(
                "# Docs\n\n## API <!-- hidden --> v2\n",
                "docs/index.md",
            )


if __name__ == "__main__":
    unittest.main()
