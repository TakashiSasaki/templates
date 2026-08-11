from __future__ import annotations

import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError, ParsedLink


class MarkdownUrlReviewTests(unittest.TestCase):
    def test_markdown_destination_escapes_are_normalized_before_resolution(self) -> None:
        entries = {"docs/overview.md": ("blob", "100644", "a" * 40)}
        for target in (r"overview\.md", "overview&#46;md"):
            with self.subTest(target=target):
                resolved = navigation.resolve_link(
                    "docs/index.md",
                    ParsedLink(
                        label="Overview",
                        raw_target=target,
                        description="Read it.",
                        section=None,
                        line=2,
                    ),
                    entries,
                )
                self.assertEqual(resolved["kind"], "file")
                self.assertEqual(resolved["target"], "docs/overview.md")

    def test_invalid_numeric_ipv4_hosts_are_rejected(self) -> None:
        for target in (
            "https://256.1.1.1/path",
            "https://4294967296/path",
        ):
            with self.subTest(target=target):
                with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
                    navigation.resolve_link(
                        "docs/index.md",
                        ParsedLink(
                            label="External",
                            raw_target=target,
                            description="Invalid numeric host.",
                            section=None,
                            line=2,
                        ),
                        {},
                    )

    def test_valid_browser_numeric_ipv4_forms_remain_accepted(self) -> None:
        for target in (
            "https://127.0.0.1/path",
            "https://2130706433/path",
        ):
            with self.subTest(target=target):
                resolved = navigation.resolve_link(
                    "docs/index.md",
                    ParsedLink(
                        label="External",
                        raw_target=target,
                        description="Valid numeric host.",
                        section=None,
                        line=2,
                    ),
                    {},
                )
                self.assertEqual(resolved["kind"], "external")

    def test_unicode_line_separators_are_rejected_before_markdown_parsing(self) -> None:
        for separator in ("\u2028", "\u2029"):
            with self.subTest(separator=separator):
                content = f"# Docs{separator}## Hidden\n".encode("utf-8")
                with self.assertRaisesRegex(
                    IndexNavigationError,
                    "non-Markdown line separator",
                ):
                    navigation.decode_index_text(content, "docs/index.md")

    def test_crlf_and_cr_are_normalized_as_markdown_line_endings(self) -> None:
        parsed = navigation.parse_index(
            "# Docs\r\n\r## Guides\r\n* [Overview](overview.md) - Read it.\r\n",
            "docs/index.md",
        )
        self.assertEqual(parsed.title, "Docs")
        self.assertEqual(parsed.sections[0].title, "Guides")
        self.assertEqual(parsed.links[0].label, "Overview")


if __name__ == "__main__":
    unittest.main()
