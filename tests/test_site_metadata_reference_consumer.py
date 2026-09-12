import unittest
from pathlib import Path

from scripts.finalize_site_metadata import SiteMetadataError, ensure_reference_consumer_anchor


TARGET = "self-hosting-reference-consumer"


class ReferenceConsumerMetadataTests(unittest.TestCase):
    def test_preserves_renderer_heading_and_fragment(self):
        source = (
            '<html><body><main><h2 id="self-hosting-reference-consumer">'
            'Self-hosting reference consumer'
            '<a class="headerlink" href="#self-hosting-reference-consumer">¶</a>'
            "</h2></main></body></html>"
        )
        rendered = ensure_reference_consumer_anchor(source, Path("coexistence/index.html"))
        self.assertEqual(source, rendered)
        self.assertEqual(rendered.count(f'id="{TARGET}"'), 1)
        self.assertNotIn("<span id=", rendered)

    def test_preserves_japanese_renderer_heading_and_fragment(self):
        source = (
            '<html><body><main><h2 id="self-hosting-reference-consumer">'
            "自己ホスティングの参照 consumer"
            '<a class="headerlink" href="#self-hosting-reference-consumer">¶</a>'
            "</h2></main></body></html>"
        )
        rendered = ensure_reference_consumer_anchor(source, Path("ja/coexistence/index.html"))
        self.assertEqual(source, rendered)

    def test_missing_renderer_heading_fails_closed(self):
        source = (
            '<html><body><main><span id="self-hosting-reference-consumer"></span>'
            "<h2>Self-hosting reference consumer</h2></main></body></html>"
        )
        with self.assertRaisesRegex(SiteMetadataError, "expected exactly one h2#self-hosting-reference-consumer"):
            ensure_reference_consumer_anchor(source, Path("coexistence/index.html"))

    def test_duplicate_renderer_headings_fail_closed(self):
        source = (
            '<html><body><main>'
            '<h2 id="self-hosting-reference-consumer">One</h2>'
            '<h2 id="self-hosting-reference-consumer">Two</h2>'
            "</main></body></html>"
        )
        with self.assertRaisesRegex(SiteMetadataError, "found 2 target element"):
            ensure_reference_consumer_anchor(source, Path("coexistence/index.html"))

    def test_non_reference_page_is_unchanged(self):
        source = '<html><body><main><span id="self-hosting-reference-consumer"></span></main></body></html>'
        self.assertEqual(
            source,
            ensure_reference_consumer_anchor(source, Path("guide/index.html")),
        )


if __name__ == "__main__":
    unittest.main()
