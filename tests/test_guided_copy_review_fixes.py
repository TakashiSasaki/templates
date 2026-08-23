from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import finalize_site_metadata  # noqa: E402
from site_chrome_locales import (  # noqa: E402
    SITE_CHROME_LOCALES,
    guided_copy_strings,
    load_site_chrome_locales,
)


SHA = "a" * 40
GITHUB_SOURCE = (
    "https://github.com/TakashiSasaki/templates/blob/" + SHA + "/docs/reference/index.md"
)
PAGE = Path("guided/skill/docs/reference/index.html")
CSP_META_PREFIX = '<meta http-equiv="Content-Security-Policy" content="'


class GuidedCopyReviewFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        chrome = load_site_chrome_locales(SITE_CHROME_LOCALES)
        cls.copy_strings = guided_copy_strings(chrome, "en")

    def test_source_link_attribute_order_is_irrelevant(self) -> None:
        source = (
            "<html><head>"
            + CSP_META_PREFIX
            + "default-src 'none'"
            + '"><title>x</title></head><body>'
            + '<p class="page-path"><span class="page-path-label">Page path:</span> '
            + '<code>/guided/skill/docs/reference/</code></p>'
            + f'<a rel="noopener" href="{GITHUB_SOURCE}" target="_blank">'
            + "immutable GitHub source</a></body></html>"
        )

        rendered = finalize_site_metadata.enhance_guided_copy_controls(
            source,
            "https://templates.moukaeritai.work/",
            PAGE,
            self.copy_strings,
        )

        self.assertIn(f'data-copy-url="{GITHUB_SOURCE}"', rendered)

    def test_csp_rejects_non_self_and_duplicate_script_sources(self) -> None:
        bad_source = "script-src " + "'" + "unsafe-inline" + "'"
        duplicate_source = "script-src 'self'; script-src 'self'"
        for policy, expected in (
            (bad_source, "guided script-src must be exactly"),
            (duplicate_source, "duplicate script-src directives"),
        ):
            with self.subTest(policy=policy):
                with self.assertRaisesRegex(
                    finalize_site_metadata.SiteMetadataError,
                    expected,
                ):
                    finalize_site_metadata.allow_guided_copy_script(
                        CSP_META_PREFIX + policy + '">',
                        PAGE,
                    )

    def test_csp_round_trip_reescapes_double_quotes_and_ampersands(self) -> None:
        policy = (
            "default-src 'none'; report-uri &quot;https://example.com/report?a=1&amp;b=2&quot;"
        )

        rendered = finalize_site_metadata.allow_guided_copy_script(
            CSP_META_PREFIX + policy + '">',
            PAGE,
        )

        self.assertIn("&quot;https://example.com/report?a=1&amp;b=2&quot;", rendered)
        self.assertNotIn('report-uri "https://example.com/', rendered)

    def test_invalid_or_mutable_github_source_urls_are_rejected(self) -> None:
        invalid_urls = (
            GITHUB_SOURCE.replace("https", "http", 1),
            GITHUB_SOURCE.replace("github.com", "example.com", 1),
            GITHUB_SOURCE + "?view=1",
            GITHUB_SOURCE + "#fragment",
            "https://github.com/TakashiSasaki/templates/blob/site/docs/reference/index.md",
        )
        for value in invalid_urls:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    finalize_site_metadata.SiteMetadataError,
                    "invalid immutable GitHub source URL",
                ):
                    finalize_site_metadata.validate_github_source_url(value, PAGE)


if __name__ == "__main__":
    unittest.main()
