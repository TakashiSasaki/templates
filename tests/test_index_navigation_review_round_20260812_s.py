import unittest
from unittest.mock import patch

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


class LatestIndexNavigationReviewRoundSTests(unittest.TestCase):
    def test_balanced_incomplete_inline_candidates_do_not_rescan_suffixes(self) -> None:
        count = 1024
        value = "[a]((" * count + " " + ")" * (2 * count)
        original = navigation._base.parse_commonmark_inline_destination
        calls = 0

        def counted(candidate: str):
            nonlocal calls
            calls += 1
            return original(candidate)

        with patch.object(navigation._base, "parse_commonmark_inline_destination", counted):
            self.assertFalse(navigation.contains_commonmark_inline_link(value))

        self.assertLessEqual(calls, 2)

    def test_unicode_hosts_preserve_empty_labels(self) -> None:
        for target in ("https://é..com/", "https://.é.com/"):
            with self.subTest(target=target):
                edge = navigation.resolve_link(
                    "docs/index.md",
                    navigation.ParsedLink(
                        label="Unicode host",
                        raw_target=target,
                        description="Preserve empty labels.",
                        section=None,
                        line=2,
                    ),
                    {},
                )
                self.assertEqual(edge["kind"], "external")

    def test_description_emptied_by_inline_decoding_is_rejected(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "empty link description"):
            navigation.normalize_link_description("&#32;", "docs/index.md", 2)

    def test_unicode_userinfo_is_encoded_before_urlsplit(self) -> None:
        edge = navigation.resolve_link(
            "docs/index.md",
            navigation.ParsedLink(
                label="Account",
                raw_target="https://user：name@example.com/",
                description="Unicode userinfo.",
                section=None,
                line=2,
            ),
            {},
        )
        self.assertEqual(edge["kind"], "external")
        self.assertEqual(edge["target"], "https://user%EF%BC%9Aname@example.com/")


if __name__ == "__main__":
    unittest.main()
