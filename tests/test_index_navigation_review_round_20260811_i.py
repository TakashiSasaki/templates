import time
import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import ParsedLink


class LatestIndexNavigationReviewRoundITests(unittest.TestCase):
    def test_leading_utf8_bom_is_consumed_before_parsing(self) -> None:
        text = navigation.decode_index_text(
            b"\xef\xbb\xbf# Docs\n",
            "docs/index.md",
        )

        self.assertEqual(text, "# Docs\n")
        self.assertEqual(navigation.parse_index(text, "docs/index.md").title, "Docs")

    def test_external_userinfo_backslash_is_percent_encoded(self) -> None:
        link = ParsedLink(
            label="External",
            raw_target=r"https://user\name@example.com/",
            description="Read it.",
            section=None,
            line=3,
        )

        resolved = navigation.resolve_link("docs/index.md", link, {})

        self.assertEqual(resolved["kind"], "external")
        self.assertEqual(
            resolved["target"],
            "https://user%5Cname@example.com/",
        )

    def test_relaxed_ascii_punycode_labels_match_whatwg_compatibility(self) -> None:
        for hostname in ("xn--abc-.com", "xn--hello-.com"):
            with self.subTest(hostname=hostname):
                link = ParsedLink(
                    label="External",
                    raw_target=f"https://{hostname}/",
                    description="Read it.",
                    section=None,
                    line=3,
                )

                resolved = navigation.resolve_link("docs/index.md", link, {})

                self.assertEqual(resolved["target"], f"https://{hostname}/")

    def test_large_opener_only_emphasis_scan_is_bounded(self) -> None:
        source = "*a " * 16_000

        started = time.perf_counter()
        result = navigation.contains_commonmark_emphasis(source)
        elapsed = time.perf_counter() - started

        self.assertFalse(result)
        self.assertLess(elapsed, 2.0)


if __name__ == "__main__":
    unittest.main()
