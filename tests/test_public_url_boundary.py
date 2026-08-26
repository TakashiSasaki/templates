from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_public_url_boundary  # noqa: E402


class PublicURLBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.site_root = Path(self.temporary_directory.name) / "site"
        self.site_root.mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, relative_path: str, content: str) -> None:
        path = self.site_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def failures(self) -> list[str]:
        return [
            path.as_posix()
            for path in check_public_url_boundary.find_retired_public_urls(
                self.site_root
            )
        ]

    def test_normal_html_rejects_retired_absolute_text_anywhere(self) -> None:
        self.write(
            "index.html",
            "<p>https://takashisasaki.github.io/templates/legacy/</p>",
        )
        self.assertEqual(["index.html"], self.failures())

    def test_normal_html_rejects_retired_root_attribute(self) -> None:
        self.write("index.html", '<a href="/templates/guide/">Guide</a>')
        self.assertEqual(["index.html"], self.failures())

    def test_source_view_allows_retired_text_when_not_an_attribute(self) -> None:
        self.write(
            "files/site/content/index.html",
            "<pre>https://takashisasaki.github.io/templates/legacy/</pre>",
        )
        self.assertEqual([], self.failures())

    def test_source_view_rejects_retired_attribute(self) -> None:
        self.write(
            "files/site/content/index.html",
            '<a href="https://templates.moukaeritai.work/templates/legacy/">Legacy</a>',
        )
        self.assertEqual(["files/site/content/index.html"], self.failures())

    def test_source_view_rejects_entity_encoded_retired_attribute(self) -> None:
        self.write(
            "files/site/content/index.html",
            '<a href="&#47;templates&#47;legacy/">Legacy</a>',
        )
        self.assertEqual(["files/site/content/index.html"], self.failures())

    def test_guided_view_uses_structural_attribute_boundary(self) -> None:
        self.write(
            "ja/guided/index.html",
            '<a href="/templates/legacy/">Legacy</a>',
        )
        self.assertEqual(["ja/guided/index.html"], self.failures())

    def test_xml_preserves_raw_text_boundary(self) -> None:
        self.write(
            "sitemap.xml",
            "<loc>https://templates.moukaeritai.work/templates/legacy/</loc>",
        )
        self.assertEqual(["sitemap.xml"], self.failures())

    def test_clean_source_view_skips_structural_parser(self) -> None:
        text = (
            "<html><body><pre>"
            "https://github.com/TakashiSasaki/templates/blob/deadbeef/README.md"
            "</pre></body></html>"
        )
        with mock.patch.object(
            check_public_url_boundary.URLAttributeParser,
            "feed",
            side_effect=AssertionError("parser should not run for a clean source view"),
        ):
            self.assertFalse(
                check_public_url_boundary.structured_retired_target_present(text)
            )

    def test_candidate_in_script_falls_back_without_false_failure(self) -> None:
        text = (
            "<html><body><script>"
            "const sample = '<a href=\"/templates/legacy/\">';"
            "</script></body></html>"
        )
        self.assertFalse(
            check_public_url_boundary.structured_retired_target_present(text)
        )


if __name__ == "__main__":
    unittest.main()
