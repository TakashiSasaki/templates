from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import finalize_site_metadata  # noqa: E402


PUBLIC_SITE_URL = "https://templates.moukaeritai.work/"


def guided_source(route: str = "/guided/") -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; style-src \'unsafe-inline\'; '
        'manifest-src \'self\'; base-uri \'none\'; form-action \'none\'">'
        '<title>Guided</title></head><body>'
        '<p class="page-path"><span class="page-path-label">Page path:</span> '
        f'<code>{route}</code></p>'
        '<main><h1>Guided</h1></main></body></html>'
    )


class GuidedPwaRuntimeTests(unittest.TestCase):
    def test_runtime_adds_minimum_csp_and_assets_once(self) -> None:
        path = Path("guided/index.html")
        rendered = finalize_site_metadata.ensure_guided_pwa_runtime(
            guided_source(),
            path,
        )

        for directive in (
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "connect-src 'self'",
            "worker-src 'self'",
            "manifest-src 'self'",
        ):
            with self.subTest(directive=directive):
                self.assertEqual(rendered.count(directive), 1)
        self.assertEqual(
            rendered.count(
                '<link rel="stylesheet" href="/stylesheets/freshness-status.css">'
            ),
            1,
        )
        self.assertEqual(
            rendered.count('<script src="/javascripts/pwa.js" defer></script>'),
            1,
        )

        second = finalize_site_metadata.ensure_guided_pwa_runtime(rendered, path)
        self.assertEqual(second, rendered)

    def test_runtime_rejects_broader_or_duplicate_csp_sources(self) -> None:
        path = Path("guided/index.html")
        cases = (
            (
                "connect-src https://example.com",
                "guided connect-src has unsupported sources",
            ),
            (
                "worker-src 'self' blob:",
                "guided worker-src has unsupported sources",
            ),
            (
                "style-src 'unsafe-inline' https://example.com",
                "guided style-src has unsupported sources",
            ),
            (
                "script-src 'self'; script-src 'self'",
                "duplicate script-src directives",
            ),
        )
        for replacement, expected in cases:
            source = guided_source().replace(
                "style-src 'unsafe-inline'",
                replacement,
                1,
            )
            with self.subTest(replacement=replacement):
                with self.assertRaisesRegex(
                    finalize_site_metadata.SiteMetadataError,
                    expected,
                ):
                    finalize_site_metadata.ensure_guided_pwa_runtime(source, path)

    def test_runtime_rejects_conflicting_asset_references(self) -> None:
        path = Path("guided/index.html")
        bad_stylesheet = guided_source().replace(
            "</head>",
            '<link rel="alternate" href="/stylesheets/freshness-status.css"></head>',
        )
        with self.assertRaisesRegex(
            finalize_site_metadata.SiteMetadataError,
            "freshness asset must be a stylesheet",
        ):
            finalize_site_metadata.ensure_guided_pwa_runtime(bad_stylesheet, path)

        duplicate_script = guided_source().replace(
            "</body>",
            '<script src="/javascripts/pwa.js"></script>'
            '<script src="/javascripts/pwa.js"></script></body>',
        )
        with self.assertRaisesRegex(
            finalize_site_metadata.SiteMetadataError,
            "duplicate guided PWA runtime scripts",
        ):
            finalize_site_metadata.ensure_guided_pwa_runtime(duplicate_script, path)

    def test_site_metadata_pass_enables_runtime_only_for_guided_page(self) -> None:
        with tempfile.TemporaryDirectory(prefix="guided-pwa-") as directory:
            root = Path(directory)
            guided = root / "index.html"
            ordinary = root / "ordinary.html"
            guided.write_text(guided_source(), encoding="utf-8")
            ordinary.write_text(
                '<!doctype html><html lang="en"><head><title>Ordinary</title></head>'
                '<body><h1>Ordinary</h1></body></html>',
                encoding="utf-8",
            )

            finalize_site_metadata.normalize_site_metadata(root, PUBLIC_SITE_URL)

            guided_html = guided.read_text(encoding="utf-8")
            ordinary_html = ordinary.read_text(encoding="utf-8")
            self.assertIn('/javascripts/guided-copy.js', guided_html)
            self.assertIn('/javascripts/pwa.js', guided_html)
            self.assertIn('/stylesheets/freshness-status.css', guided_html)
            self.assertNotIn('/javascripts/pwa.js', ordinary_html)
            self.assertNotIn('/stylesheets/freshness-status.css', ordinary_html)

    def test_metadata_failure_does_not_partially_write_other_pages(self) -> None:
        with tempfile.TemporaryDirectory(prefix="guided-pwa-") as directory:
            root = Path(directory)
            first = root / "first.html"
            second = root / "second.html"
            first.write_text(guided_source("/guided/first/"), encoding="utf-8")
            invalid_second = guided_source("/guided/second/").replace(
                "manifest-src 'self'",
                "connect-src https://example.com; manifest-src 'self'",
            )
            second.write_text(invalid_second, encoding="utf-8")
            first_before = first.read_bytes()

            with self.assertRaisesRegex(
                finalize_site_metadata.SiteMetadataError,
                "guided connect-src has unsupported sources",
            ):
                finalize_site_metadata.normalize_site_metadata(root, PUBLIC_SITE_URL)

            self.assertEqual(first.read_bytes(), first_before)


if __name__ == "__main__":
    unittest.main()
