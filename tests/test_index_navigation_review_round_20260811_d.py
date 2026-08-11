import unittest

from scripts.generate_index_navigation import IndexNavigationError, parse_index


class LatestIndexNavigationReviewRoundDTests(unittest.TestCase):
    def test_inline_code_spans_fail_closed_in_headings(self) -> None:
        for heading in ("`&amp;`", "`\\*`"):
            with self.subTest(heading=heading):
                with self.assertRaisesRegex(
                    IndexNavigationError,
                    "unsupported inline code span in heading",
                ):
                    parse_index(f"# {heading}\n", "docs/index.md")

    def test_inline_code_spans_fail_closed_in_link_labels(self) -> None:
        with self.assertRaisesRegex(
            IndexNavigationError,
            "unsupported inline code span in link label",
        ):
            parse_index(
                "# Docs\n\n* [Guide `&amp;`](overview.md) - Read it.\n",
                "docs/index.md",
            )

    def test_escaped_backticks_remain_plain_text(self) -> None:
        parsed = parse_index(
            "# Escaped \\` marker\n\n"
            "* [Guide \\`advanced\\`](overview.md) - Read it.\n",
            "docs/index.md",
        )

        self.assertEqual(parsed.title, "Escaped ` marker")
        self.assertEqual(parsed.links[0].label, "Guide `advanced`")

    def test_balanced_brackets_are_valid_in_reserved_link_labels(self) -> None:
        parsed = parse_index(
            "# Docs\n\n* [Guide [advanced]](overview.md) - Read it.\n",
            "docs/index.md",
        )

        self.assertEqual(parsed.links[0].label, "Guide [advanced]")
        self.assertEqual(parsed.links[0].raw_target, "overview.md")

    def test_nested_links_in_reserved_link_labels_fail_closed(self) -> None:
        with self.assertRaisesRegex(
            IndexNavigationError,
            "nested inline link in link label",
        ):
            parse_index(
                "# Docs\n\n"
                "* [Guide [advanced](inner.md)](overview.md) - Read it.\n",
                "docs/index.md",
            )

    def test_escaped_outer_label_terminator_keeps_specific_diagnostic(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "escaped link-label terminator"):
            parse_index(
                "# Docs\n\n* [Guide\\](overview.md) - Read it.\n",
                "docs/index.md",
            )

    def test_unbalanced_link_label_openers_still_fail_closed(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "unsupported index.md content"):
            parse_index(
                "# Docs\n\n* [Guide [advanced](overview.md) - Read it.\n",
                "docs/index.md",
            )


if __name__ == "__main__":
    unittest.main()
