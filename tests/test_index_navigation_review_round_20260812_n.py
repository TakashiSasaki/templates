import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


class LatestIndexNavigationReviewRoundNTests(unittest.TestCase):
    def test_escaped_looking_code_span_closer_still_hides_label_terminator(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "unsupported index.md content"):
            navigation.parse_index(
                "# Docs\n\n* [foo `](evil) - fake\\`\n",
                "docs/index.md",
            )

    def test_internal_double_hyphen_remains_valid_commonmark_html_comment(self) -> None:
        self.assertTrue(navigation.contains_commonmark_raw_html("<!-- a--b -->"))
        with self.assertRaisesRegex(IndexNavigationError, "unsupported raw HTML in heading"):
            navigation.parse_index(
                "# Docs <!-- a--b -->\n",
                "docs/index.md",
            )


if __name__ == "__main__":
    unittest.main()
