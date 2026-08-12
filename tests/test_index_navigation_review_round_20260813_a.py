import unittest
from unittest.mock import patch

from scripts import generate_index_navigation as navigation


class LatestIndexNavigationReviewRound20260813ATests(unittest.TestCase):
    def test_many_distinct_unmatched_backtick_runs_are_indexed_once(self) -> None:
        value = " ".join("`" * length for length in range(1, 701))
        original = navigation._backtick_run_length
        calls = 0

        def counted(candidate: str, start: int) -> int:
            nonlocal calls
            calls += 1
            return original(candidate, start)

        with patch.object(navigation, "_backtick_run_length", counted):
            self.assertEqual(navigation.commonmark_code_span_closers(value), {})

        self.assertLessEqual(calls, 700)

    def test_code_span_inside_unmatched_bracket_keeps_literal_link_syntax(self) -> None:
        source = "[draft `](foo)`"
        self.assertFalse(navigation.contains_commonmark_inline_link(source))
        self.assertEqual(
            navigation.normalize_link_description(source, "docs/index.md", 2),
            "[draft ](foo)",
        )

    def test_real_link_after_code_span_inside_label_is_still_detected(self) -> None:
        source = "[draft `](literal)` text](target.md)"
        self.assertTrue(navigation.contains_commonmark_inline_link(source))

    def test_inline_destination_probe_reaches_preserved_implementation_binding(self) -> None:
        original = navigation._base.parse_commonmark_inline_destination
        calls = 0

        def counted(candidate: str):
            nonlocal calls
            calls += 1
            return original(candidate)

        with patch.object(navigation._base, "parse_commonmark_inline_destination", counted):
            self.assertTrue(
                navigation.contains_commonmark_inline_link("[x](<target.md>)")
            )

        self.assertGreater(calls, 0)


if __name__ == "__main__":
    unittest.main()
