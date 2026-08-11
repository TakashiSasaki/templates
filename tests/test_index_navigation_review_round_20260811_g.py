import unittest

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError, ParsedLink


class LatestIndexNavigationReviewRoundGTests(unittest.TestCase):
    def test_intraword_underscore_is_plain_rendered_text(self) -> None:
        parsed = navigation.parse_index(
            "# API_v2\n\n* [Guide_v2](overview.md) - API_v2 guide.\n",
            "docs/index.md",
        )

        self.assertEqual(parsed.title, "API_v2")
        self.assertEqual(parsed.links[0].label, "Guide_v2")
        self.assertEqual(parsed.links[0].description, "API_v2 guide.")

    def test_actual_emphasis_remains_rejected(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "unsupported emphasis in heading"):
            navigation.parse_index(
                "# Docs\n\n## *API*\n",
                "docs/index.md",
            )

    def test_external_spaces_are_percent_encoded_like_rendered_href(self) -> None:
        pointy = ParsedLink(
            label="External",
            raw_target="<https://example.com/a b>",
            description="Read it.",
            section=None,
            line=3,
        )
        entity = ParsedLink(
            label="External",
            raw_target="https://example.com/a&#32;b",
            description="Read it.",
            section=None,
            line=4,
        )

        self.assertEqual(
            navigation.resolve_link("docs/index.md", pointy, {})["target"],
            "https://example.com/a%20b",
        )
        self.assertEqual(
            navigation.resolve_link("docs/index.md", entity, {})["target"],
            "https://example.com/a%20b",
        )

    def test_malformed_ascii_punycode_host_is_rejected(self) -> None:
        malformed = ParsedLink(
            label="External",
            raw_target="https://xn--.com/",
            description="Read it.",
            section=None,
            line=3,
        )
        valid = ParsedLink(
            label="External",
            raw_target="https://xn--53h.example/",
            description="Read it.",
            section=None,
            line=4,
        )

        with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
            navigation.resolve_link("docs/index.md", malformed, {})
        self.assertEqual(
            navigation.resolve_link("docs/index.md", valid, {})["target"],
            "https://xn--53h.example/",
        )

    def test_optional_inline_link_title_is_accepted_and_ignored_by_graph(self) -> None:
        parsed = navigation.parse_index(
            '# Docs\n\n* [Overview](<overview.md> "Open overview") - Read it.\n',
            "docs/index.md",
        )
        self.assertEqual(parsed.links[0].raw_target, "<overview.md>")

        resolved = navigation.resolve_link(
            "docs/index.md",
            parsed.links[0],
            {"docs/overview.md": ("blob", "100644", "a" * 40)},
        )
        self.assertEqual(
            resolved,
            {"kind": "file", "target": "docs/overview.md", "fragment": None},
        )


if __name__ == "__main__":
    unittest.main()
