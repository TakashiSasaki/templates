import unittest
from urllib.parse import urlsplit

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


class LatestIndexNavigationReviewRoundTTests(unittest.TestCase):
    def test_arabic_extended_b_still_triggers_the_whatwg_bidi_rule(self) -> None:
        for codepoint in range(0x0870, 0x088F):
            hostname = f"a{chr(codepoint)}b.com"
            target = f"https://{hostname}/"
            with self.subTest(codepoint=f"U+{codepoint:04X}"):
                with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
                    navigation.canonicalize_whatwg_domain(
                        hostname,
                        "docs/index.md",
                        2,
                        target,
                    )
                with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
                    navigation.validate_external_location(
                        urlsplit(target),
                        "docs/index.md",
                        2,
                        target,
                    )

        with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
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
            "https://ࡰب.com/",
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
