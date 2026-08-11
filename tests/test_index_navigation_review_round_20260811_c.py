import unittest

from scripts.generate_index_navigation import (
    IndexNavigationError,
    ParsedLink,
    parse_index,
    resolve_link,
)


class LatestIndexNavigationReviewTests(unittest.TestCase):
    def test_heading_entities_are_normalized_before_duplicate_comparison(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "duplicate section heading"):
            parse_index(
                "# Docs &amp; Guides\n\n"
                "## API &amp; Usage\n"
                "## API & Usage\n",
                "docs/index.md",
            )

    def test_heading_text_matches_commonmark_rendered_text(self) -> None:
        parsed = parse_index(
            "# Docs &amp; Guides\n\n## Escaped \\# marker\n",
            "docs/index.md",
        )

        self.assertEqual(parsed.title, "Docs & Guides")
        self.assertEqual(parsed.sections[0].title, "Escaped # marker")

    def test_unbalanced_link_label_opener_does_not_use_inner_image_terminator(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "unsupported index.md content"):
            parse_index(
                "# Docs\n\n* [prefix ![Diagram](diagram.png) - See it.\n",
                "docs/index.md",
            )

    def test_escaped_brackets_remain_valid_in_reserved_link_labels(self) -> None:
        parsed = parse_index(
            "# Docs\n\n* [Guide \\[advanced\\]](overview.md) - Read it.\n",
            "docs/index.md",
        )

        self.assertEqual(parsed.links[0].label, "Guide [advanced]")
        self.assertEqual(parsed.links[0].raw_target, "overview.md")

    def test_scoped_ipv6_external_host_fails_closed(self) -> None:
        link = ParsedLink(
            label="Scoped IPv6",
            raw_target="https://[fe80::1%25eth0]/",
            description="Scoped host.",
            section=None,
            line=2,
        )
        with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
            resolve_link("docs/index.md", link, {})

    def test_plain_ipv6_external_host_remains_valid(self) -> None:
        link = ParsedLink(
            label="IPv6",
            raw_target="https://[fe80::1]/",
            description="IPv6 host.",
            section=None,
            line=2,
        )
        self.assertEqual(
            resolve_link("docs/index.md", link, {}),
            {
                "kind": "external",
                "target": "https://[fe80::1]/",
                "fragment": None,
            },
        )

    def test_contextual_joiners_are_not_silently_removed_by_idna(self) -> None:
        for joiner in ("\u200c", "\u200d"):
            with self.subTest(joiner=hex(ord(joiner))):
                link = ParsedLink(
                    label="Joiner host",
                    raw_target=f"https://a{joiner}b.com/",
                    description="Invalid contextual joiner.",
                    section=None,
                    line=2,
                )
                with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
                    resolve_link("docs/index.md", link, {})


if __name__ == "__main__":
    unittest.main()
