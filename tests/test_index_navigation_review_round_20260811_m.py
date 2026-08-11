import time
import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


class LatestIndexNavigationReviewRoundMTests(unittest.TestCase):
    def test_code_span_bracket_does_not_terminate_reserved_link_label(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "unsupported index.md content"):
            navigation.parse_index(
                "# Docs\n\n* [foo `](evil) - fake`\n",
                "docs/index.md",
            )

    def test_code_span_inside_valid_outer_label_still_fails_closed(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "unsupported inline code span in link label"):
            navigation.parse_index(
                "# Docs\n\n* [foo `]` bar](overview.md) - Read it.\n",
                "docs/index.md",
            )

    def test_bare_destination_more_than_32_balanced_levels_remains_accepted(self) -> None:
        destination = "(" * 33 + "deep" + ")" * 33
        parsed = navigation.parse_index(
            f"# Docs\n\n* [Deep]({destination}) - Read it.\n",
            "docs/index.md",
        )

        self.assertEqual(parsed.links[0].raw_target, destination)

    def test_unterminated_raw_html_opener_scan_is_bounded(self) -> None:
        source = "<!--x" * 40_000

        started = time.perf_counter()
        result = navigation.contains_commonmark_raw_html(source)
        elapsed = time.perf_counter() - started

        self.assertFalse(result)
        self.assertLess(elapsed, 2.0)


if __name__ == "__main__":
    unittest.main()
