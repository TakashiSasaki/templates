import unittest

from scripts.generate_index_navigation import (
    IndexNavigationError,
    ParsedLink,
    parse_index,
    resolve_link,
)


def external_link(target: str) -> ParsedLink:
    return ParsedLink(
        label="External",
        raw_target=target,
        description="External reference.",
        section=None,
        line=2,
    )


class LatestIndexNavigationReviewRoundBTests(unittest.TestCase):
    def test_percent_encoded_external_hostname_is_decoded_for_validation(self) -> None:
        resolved = resolve_link(
            "docs/index.md",
            external_link("https://example%2ecom/spec"),
            {},
        )

        self.assertEqual(
            resolved,
            {
                "kind": "external",
                "target": "https://example%2ecom/spec",
                "fragment": None,
            },
        )

    def test_malformed_or_forbidden_percent_encoded_hosts_fail_closed(self) -> None:
        for target in (
            "https://example%ZZcom/spec",
            "https://example%2fcom/spec",
            "https://example%00com/spec",
        ):
            with self.subTest(target=target):
                with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
                    resolve_link("docs/index.md", external_link(target), {})

    def test_escaped_label_bracket_uses_later_real_terminator(self) -> None:
        parsed = parse_index(
            "# Docs\n\n* [Guide \\] advanced](overview.md) - Read overview.\n",
            "docs/index.md",
        )

        self.assertEqual(len(parsed.links), 1)
        self.assertEqual(parsed.links[0].label, "Guide ] advanced")
        self.assertEqual(parsed.links[0].raw_target, "overview.md")


if __name__ == "__main__":
    unittest.main()
