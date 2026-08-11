import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


class LatestIndexNavigationReviewRoundLTests(unittest.TestCase):
    def test_decoded_non_markdown_line_separators_fail_closed(self) -> None:
        for text, expected in (
            ("# API &#x2028; draft\n", "heading contains a disallowed control character"),
            (
                "# Docs\n\n* [Guide &#x2029; draft](overview.md) - Read it.\n",
                "link label contains a disallowed control character",
            ),
            (
                "# Docs\n\n* [Guide](overview.md) - Read&#x2028;it.\n",
                "link description contains a disallowed control character",
            ),
        ):
            with self.subTest(text=text):
                with self.assertRaisesRegex(IndexNavigationError, expected):
                    navigation.parse_index(text, "docs/index.md")

        for raw_target, expected in (
            ("over%E2%80%A8view.md", "link path contains a disallowed control character"),
            ("overview.md#part%E2%80%A9two", "link fragment contains a disallowed control character"),
        ):
            with self.subTest(raw_target=raw_target):
                link = navigation.ParsedLink(
                    label="Guide",
                    raw_target=raw_target,
                    description="Read it.",
                    section=None,
                    line=3,
                )
                with self.assertRaisesRegex(IndexNavigationError, expected):
                    navigation.resolve_link(
                        "docs/index.md",
                        link,
                        {"docs/overview.md": ("blob", "100644", "a" * 40)},
                    )

    def test_unmatched_backticks_remain_literal_text(self) -> None:
        heading = navigation.parse_index(
            "# API `draft\n",
            "docs/index.md",
        )
        self.assertEqual(heading.title, "API `draft")

        label = navigation.parse_index(
            "# Docs\n\n* [Guide `draft](overview.md) - Read it.\n",
            "docs/index.md",
        )
        self.assertEqual(label.links[0].label, "Guide `draft")

        description = navigation.parse_index(
            "# Docs\n\n* [Guide](overview.md) - Read `draft.\n",
            "docs/index.md",
        )
        self.assertEqual(description.links[0].description, "Read `draft.")

    def test_actual_code_spans_still_fail_closed(self) -> None:
        for text, expected in (
            ("# API `draft`\n", "unsupported inline code span in heading"),
            (
                "# Docs\n\n* [Guide `draft`](overview.md) - Read it.\n",
                "unsupported inline code span in link label",
            ),
            (
                "# Docs\n\n* [Guide](overview.md) - Read `draft`.\n",
                "unsupported inline code span in link description",
            ),
        ):
            with self.subTest(text=text):
                with self.assertRaisesRegex(IndexNavigationError, expected):
                    navigation.parse_index(text, "docs/index.md")

    def test_unicode_domain_validity_rejects_combining_and_bidi_failures(self) -> None:
        for raw_target in (
            "https://\u0301a.com/",
            "https://אבa.com/",
        ):
            with self.subTest(raw_target=raw_target):
                link = navigation.ParsedLink(
                    label="External",
                    raw_target=raw_target,
                    description="Read it.",
                    section=None,
                    line=3,
                )
                with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
                    navigation.resolve_link("docs/index.md", link, {})

    def test_uts46_valid_symbol_domain_remains_accepted(self) -> None:
        link = navigation.ParsedLink(
            label="External",
            raw_target="https://☕.example/",
            description="Read it.",
            section=None,
            line=3,
        )

        self.assertEqual(
            navigation.resolve_link("docs/index.md", link, {}),
            {
                "kind": "external",
                "target": "https://%E2%98%95.example/",
                "fragment": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
