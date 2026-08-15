from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_freshness_metadata  # noqa: E402


SITE_REVISION = "a" * 40


class FreshnessReviewRegressionTests(unittest.TestCase):
    def test_head_annotation_ignores_head_like_text_in_script_content(self) -> None:
        source = (
            "<html>\n"
            "<head>\n"
            "<title>Test</title>\n"
            "</head>\n"
            "<body>\n"
            '<script>const example = "</head>";</script>\n'
            "</body>\n"
            "</html>\n"
        )

        updated = generate_freshness_metadata.annotate_site_revision(
            source,
            SITE_REVISION,
            Path("index.html"),
        )

        marker = (
            '<meta name="templates-site-revision" '
            f'content="{SITE_REVISION}">'
        )
        self.assertEqual(updated.count(marker), 1)
        self.assertLess(updated.index(marker), updated.index("</head>"))
        self.assertIn('<script>const example = "</head>";</script>', updated)

    def test_head_annotation_uses_parser_line_and_column_position(self) -> None:
        source = (
            "<!doctype html>\n"
            "<html>\n"
            "  <head>\n"
            "    <title>Test</title>\n"
            "  </head>\n"
            "  <body></body>\n"
            "</html>\n"
        )

        position = generate_freshness_metadata.head_close_offset(
            source,
            Path("index.html"),
        )

        self.assertTrue(source[position:].startswith("</head>"))

    def test_source_offset_matches_html_parser_with_nonstandard_newlines(self) -> None:
        marker = (
            '<meta name="templates-site-revision" '
            f'content="{SITE_REVISION}">'
        )
        cases = {
            "crlf-and-lone-cr": (
                "<!doctype html>\r\n<html>\r\n<head>\r"
                "<title>Test</title>\r\n</head><body></body></html>"
            ),
            "unicode-line-separator": (
                "<!doctype html>\n<html>\n<head>\u2028"
                "<title>Test</title>\u2028</head><body></body></html>"
            ),
        }

        for name, source in cases.items():
            with self.subTest(name=name):
                updated = generate_freshness_metadata.annotate_site_revision(
                    source,
                    SITE_REVISION,
                    Path("index.html"),
                )
                self.assertEqual(updated.count(marker), 1)
                self.assertEqual(
                    updated.index(marker) + len(marker) + 1,
                    updated.index("</head>"),
                )

    def test_service_worker_guards_capability_message_target(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")

        self.assertIn(
            'typeof event.source.postMessage !== "function"',
            worker,
        )
        self.assertIn(
            'event.data?.type !== "templates:get-freshness-capabilities"',
            worker,
        )


if __name__ == "__main__":
    unittest.main()
