from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import finalize_site_metadata  # noqa: E402


TARGET = "https://templates.moukaeritai.work/guide/"


class CanonicalParserFastPathTests(unittest.TestCase):
    def test_rewrites_only_the_structural_canonical_tag(self) -> None:
        source = (
            "<html><head>"
            '<link rel="stylesheet" href="/style.css">'
            '<link href="https://old.example/guide/" rel="alternate canonical">'
            "</head><body>guide</body></html>"
        )

        rendered = finalize_site_metadata.rewrite_canonical_link(
            source,
            TARGET,
            Path("guide/index.html"),
        )

        self.assertIn('<link rel="stylesheet" href="/style.css">', rendered)
        self.assertIn(
            f'<link href="{TARGET}" rel="alternate canonical">',
            rendered,
        )
        self.assertNotIn("https://old.example/guide/", rendered)

    def test_comment_only_canonical_candidate_remains_fail_closed(self) -> None:
        source = (
            "<html><head>"
            '<!-- <link rel="canonical" href="https://fake.example/"> -->'
            "</head><body></body></html>"
        )

        with self.assertRaisesRegex(
            finalize_site_metadata.SiteMetadataError,
            "canonical URL normalization failed",
        ):
            finalize_site_metadata.rewrite_canonical_link(
                source,
                TARGET,
                Path("index.html"),
            )

    def test_script_text_canonical_candidate_remains_fail_closed(self) -> None:
        source = (
            "<html><head><script>"
            'const sample = \'<link rel="canonical" href="https://fake.example/">\';'
            "</script></head><body></body></html>"
        )

        with self.assertRaisesRegex(
            finalize_site_metadata.SiteMetadataError,
            "canonical URL normalization failed",
        ):
            finalize_site_metadata.rewrite_canonical_link(
                source,
                TARGET,
                Path("index.html"),
            )

    def test_body_canonical_preserves_existing_structural_behavior(self) -> None:
        source = (
            "<html><head></head><body>"
            '<link rel="canonical" href="https://old.example/guide/">'
            "</body></html>"
        )

        rendered = finalize_site_metadata.rewrite_canonical_link(
            source,
            TARGET,
            Path("guide/index.html"),
        )

        self.assertIn(f'<link rel="canonical" href="{TARGET}">', rendered)

    def test_duplicate_canonical_candidates_are_rejected(self) -> None:
        source = (
            "<html><head>"
            '<link rel="canonical" href="https://one.example/">'
            '<link rel="canonical" href="https://two.example/">'
            "</head><body></body></html>"
        )

        with self.assertRaisesRegex(
            finalize_site_metadata.SiteMetadataError,
            "expected at most one canonical link, found 2",
        ):
            finalize_site_metadata.rewrite_canonical_link(
                source,
                TARGET,
                Path("index.html"),
            )

    def test_full_document_is_not_reparsed_after_structural_match(self) -> None:
        source = (
            "<html><head>"
            '<link rel="canonical" href="https://old.example/guide/">'
            "</head><body>"
            + ("large body text " * 1000)
            + "</body></html>"
        )
        original = finalize_site_metadata.parse_head_elements
        parsed_inputs: list[str] = []

        def record(value: str):
            parsed_inputs.append(value)
            return original(value)

        with mock.patch.object(
            finalize_site_metadata,
            "parse_head_elements",
            side_effect=record,
        ):
            finalize_site_metadata.rewrite_canonical_link(
                source,
                TARGET,
                Path("guide/index.html"),
            )

        self.assertNotIn(source, parsed_inputs)
        self.assertTrue(parsed_inputs)
        self.assertTrue(all(value.lstrip().lower().startswith("<link") for value in parsed_inputs))


if __name__ == "__main__":
    unittest.main()
