import unittest
from urllib.parse import urlsplit

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


class LatestIndexNavigationReviewRoundQTests(unittest.TestCase):
    def test_unicode_host_preserves_multiple_terminal_dots(self) -> None:
        target = "https://é.999../"
        self.assertEqual(
            navigation.canonicalize_whatwg_domain(
                "é.999..",
                "docs/index.md",
                2,
                target,
            ),
            "xn--9ca.999..",
        )
        navigation.validate_external_location(
            urlsplit(target),
            "docs/index.md",
            2,
            target,
        )

    def test_noncanonical_ascii_alabel_is_rejected_after_uts46_remapping(self) -> None:
        target = "https://xn--a-6ha.com/"
        with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
            navigation.validate_external_location(
                urlsplit(target),
                "docs/index.md",
                2,
                target,
            )

    def test_pointy_destination_preserves_leading_space_before_url_parsing(self) -> None:
        self.assertEqual(
            navigation.decode_markdown_destination(
                "< overview.md>",
                "docs/index.md",
                2,
            ),
            "%20overview.md",
        )
        self.assertEqual(
            navigation.decode_markdown_destination(
                "< https://example.com>",
                "docs/index.md",
                3,
            ),
            "%20https://example.com",
        )

        edge = navigation.resolve_link(
            "docs/index.md",
            navigation.ParsedLink(
                label="Overview",
                raw_target="< overview.md>",
                description="Read the spaced filename.",
                section=None,
                line=2,
            ),
            {"docs/ overview.md": ("blob", "100644", "a" * 40)},
        )
        self.assertEqual(edge["kind"], "file")
        self.assertEqual(edge["target"], "docs/ overview.md")


if __name__ == "__main__":
    unittest.main()
