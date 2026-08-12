import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


class LatestIndexNavigationReviewRoundRTests(unittest.TestCase):
    def test_incomplete_inline_link_candidates_do_not_rescan_suffixes(self) -> None:
        value = "[a](" * 2048
        original = navigation.parse_commonmark_inline_destination
        calls = 0

        def counted(candidate: str):
            nonlocal calls
            calls += 1
            return original(candidate)

        with patch.object(navigation, "parse_commonmark_inline_destination", counted):
            self.assertFalse(navigation.contains_commonmark_inline_link(value))

        self.assertLessEqual(calls, 2)

    def test_pointy_inline_destination_rejects_unescaped_inner_less_than(self) -> None:
        self.assertFalse(
            navigation.contains_commonmark_inline_link("[draft](<a<b>)")
        )

    def test_percent_escape_is_rejected_inside_bracketed_ipv6_host(self) -> None:
        link = navigation.ParsedLink(
            label="IPv6",
            raw_target="https://[::%31]/",
            description="Invalid browser IPv6 host.",
            section=None,
            line=2,
        )
        with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
            navigation.resolve_link("docs/index.md", link, {})

    def test_duplicate_git_tree_paths_fail_closed_before_indexing(self) -> None:
        duplicate_entries = [
            SimpleNamespace(
                path=b"docs/index.md",
                kind="blob",
                mode="100644",
                object_id="a" * 40,
            ),
            SimpleNamespace(
                path=b"docs/index.md",
                kind="blob",
                mode="100644",
                object_id="b" * 40,
            ),
        ]
        with (
            patch.object(navigation, "checked_revision", return_value="f" * 40),
            patch.object(
                navigation,
                "read_entries_at_revision",
                return_value=duplicate_entries,
            ),
            self.assertRaisesRegex(IndexNavigationError, "duplicate Git tree path"),
        ):
            navigation.collect_provider_graph("skill", Path("/tmp/provider"))

    def test_userinfo_brackets_are_encoded_before_urlsplit(self) -> None:
        edge = navigation.resolve_link(
            "docs/index.md",
            navigation.ParsedLink(
                label="Account",
                raw_target="https://user[name@example.com/",
                description="Userinfo bracket.",
                section=None,
                line=2,
            ),
            {},
        )
        self.assertEqual(edge["kind"], "external")
        self.assertEqual(edge["target"], "https://user%5Bname@example.com/")


if __name__ == "__main__":
    unittest.main()
