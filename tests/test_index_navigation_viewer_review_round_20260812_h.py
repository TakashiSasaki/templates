import unittest

from scripts.generate_index_navigation_viewer import heading_anchors


class LatestIndexNavigationViewerReviewRoundHTests(unittest.TestCase):
    def test_higher_explicit_suffix_does_not_skip_first_free_suffix(self) -> None:
        self.assertEqual(
            heading_anchors(["A", "A_2", "A"]),
            ["a", "a_2", "a_1"],
        )

    def test_duplicate_explicit_suffix_still_increments_from_that_suffix(self) -> None:
        self.assertEqual(
            heading_anchors(["A_2", "A_2"]),
            ["a_2", "a_3"],
        )

    def test_existing_low_suffixes_are_still_skipped(self) -> None:
        self.assertEqual(
            heading_anchors(["A", "A", "A_3", "A"]),
            ["a", "a_1", "a_3", "a_2"],
        )


if __name__ == "__main__":
    unittest.main()
