import unittest
from urllib.parse import urlsplit

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


class LatestIndexNavigationReviewRoundTTests(unittest.TestCase):
    def test_browser_valid_arabic_extended_b_in_ltr_labels_is_accepted(self) -> None:
        for hostname in (
            "a\u0870b.com",
            "a\u088eb.com",
        ):
            with self.subTest(hostname=hostname):
                canonical = navigation.canonicalize_whatwg_domain(
                    hostname,
                    "docs/index.md",
                    2,
                    f"https://{hostname}/",
                )
                navigation.validate_external_location(
                    urlsplit(f"https://{hostname}/"),
                    "docs/index.md",
                    2,
                    f"https://{hostname}/",
                )
                self.assertTrue(canonical.startswith("xn--"))

        navigation.validate_ascii_punycode_labels(
            "xn--ab-h8e.com",
            "docs/index.md",
            2,
            "https://xn--ab-h8e.com/",
        )

    def test_true_mixed_direction_hosts_remain_rejected(self) -> None:
        for target in (
            "https://aبb.com/",
            "https://אבa.com/",
            "https://xn--a-zhcd.com/",
        ):
            with self.subTest(target=target):
                with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
                    navigation.validate_external_location(
                        urlsplit(target),
                        "docs/index.md",
                        2,
                        target,
                    )


if __name__ == "__main__":
    unittest.main()
