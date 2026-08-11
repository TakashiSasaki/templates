from __future__ import annotations

import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError, ParsedLink


class MarkdownUrlReviewTests(unittest.TestCase):
    def resolve(self, target: str, entries=None):
        return navigation.resolve_link(
            "docs/index.md",
            ParsedLink(
                label="Target",
                raw_target=target,
                description="Review boundary.",
                section=None,
                line=2,
            ),
            {} if entries is None else entries,
        )

    def test_markdown_destination_escapes_are_normalized_before_resolution(self) -> None:
        entries = {"docs/overview.md": ("blob", "100644", "a" * 40)}
        for target in (r"overview\.md", "overview&#46;md"):
            with self.subTest(target=target):
                resolved = self.resolve(target, entries)
                self.assertEqual(resolved["kind"], "file")
                self.assertEqual(resolved["target"], "docs/overview.md")

    def test_only_semicolon_terminated_commonmark_entities_are_decoded(self) -> None:
        for target in ("overview&copy.md", "overview&#65.md"):
            with self.subTest(target=target):
                self.assertEqual(
                    navigation.decode_markdown_destination(target, "docs/index.md", 2),
                    target,
                )
        self.assertEqual(
            navigation.decode_markdown_destination(
                "overview&copy;.md", "docs/index.md", 2
            ),
            "overview©.md",
        )

    def test_unbalanced_bare_destination_parentheses_are_rejected(self) -> None:
        entries = {"docs/foo(bar.md": ("blob", "100644", "a" * 40)}
        with self.assertRaisesRegex(IndexNavigationError, "unbalanced link destination"):
            self.resolve("foo(bar.md", entries)

        balanced_entries = {"docs/foo(bar).md": ("blob", "100644", "b" * 40)}
        resolved = self.resolve("foo(bar).md", balanced_entries)
        self.assertEqual(resolved["target"], "docs/foo(bar).md")

    def test_invalid_numeric_ipv4_hosts_are_rejected(self) -> None:
        for target in (
            "https://256.1.1.1/path",
            "https://4294967296/path",
            "https://２５６.１.１.１/path",
        ):
            with self.subTest(target=target):
                with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
                    self.resolve(target)

    def test_valid_browser_numeric_ipv4_forms_remain_accepted(self) -> None:
        for target in (
            "https://127.0.0.1/path",
            "https://2130706433/path",
            "https://１２７.０.０.１/path",
        ):
            with self.subTest(target=target):
                resolved = self.resolve(target)
                self.assertEqual(resolved["kind"], "external")

    def test_empty_query_delimiters_are_rejected(self) -> None:
        entries = {"docs/overview.md": ("blob", "100644", "a" * 40)}
        for target in (
            "overview.md?",
            "overview.md?#section",
            "https://example.com/spec?",
            "https://example.com/spec?#section",
        ):
            with self.subTest(target=target):
                with self.assertRaisesRegex(IndexNavigationError, "must not contain a query"):
                    self.resolve(target, entries)

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
