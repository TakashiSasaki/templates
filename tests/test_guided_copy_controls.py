from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import finalize_site_metadata  # noqa: E402


CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; manifest-src 'self'; "
    "base-uri 'none'; form-action 'none'"
)
PUBLIC_SITE_URL = "https://templates.moukaeritai.work/"
GITHUB_SOURCE = (
    "https://github.com/TakashiSasaki/templates/blob/"
    + ("a" * 40)
    + "/docs/reference/index.md"
)


def guided_page(*, page_path: str, github_source: str | None = None) -> str:
    source_link = ""
    if github_source is not None:
        source_link = (
            f'<a href="{github_source}" target="_blank" rel="noopener">'
            "immutable GitHub source</a>"
        )
    return (
        "<!doctype html><html><head>"
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
        "<title>Guided</title></head><body><main>"
        '<p class="page-path"><span class="page-path-label">Page path:</span> '
        f"<code>{page_path}</code></p>"
        f"<div class=\"meta\">{source_link}</div>"
        "</main></body></html>"
    )


class GuidedCopyControlTests(unittest.TestCase):
    def test_index_page_gets_immutable_github_and_public_copy_targets(self) -> None:
        rendered = finalize_site_metadata.enhance_guided_copy_controls(
            guided_page(
                page_path="/guided/skill/docs/reference/",
                github_source=GITHUB_SOURCE,
            ),
            PUBLIC_SITE_URL,
            Path("guided/skill/docs/reference/index.html"),
        )

        self.assertIn('data-copy-name="GitHub URL"', rendered)
        self.assertIn(f'data-copy-url="{GITHUB_SOURCE}"', rendered)
        self.assertIn('data-copy-name="public URL"', rendered)
        self.assertIn(
            'data-copy-url="https://templates.moukaeritai.work/guided/skill/docs/reference/"',
            rendered,
        )
        self.assertIn("script-src 'self'", rendered)
        self.assertIn(
            '<script src="/javascripts/guided-copy.js" defer></script>',
            rendered,
        )

    def test_landing_has_only_the_real_public_copy_target(self) -> None:
        rendered = finalize_site_metadata.enhance_guided_copy_controls(
            guided_page(page_path="/guided/"),
            PUBLIC_SITE_URL,
            Path("guided/index.html"),
        )

        self.assertNotIn('data-copy-name="GitHub URL"', rendered)
        self.assertNotIn("Copy GitHub URL", rendered)
        self.assertIn('data-copy-name="public URL"', rendered)
        self.assertIn(
            'data-copy-url="https://templates.moukaeritai.work/guided/"',
            rendered,
        )
        self.assertEqual(rendered.count("data-copy-url="), 1)

    def test_multiple_github_sources_are_rejected_instead_of_guessed(self) -> None:
        source = guided_page(
            page_path="/guided/skill/docs/reference/",
            github_source=GITHUB_SOURCE,
        ).replace(
            "</div>",
            (
                f'<a href="{GITHUB_SOURCE}#duplicate" target="_blank" rel="noopener">'
                "immutable GitHub source</a></div>"
            ),
            1,
        )

        with self.assertRaisesRegex(
            finalize_site_metadata.SiteMetadataError,
            "multiple immutable GitHub sources",
        ):
            finalize_site_metadata.enhance_guided_copy_controls(
                source,
                PUBLIC_SITE_URL,
                Path("guided/skill/docs/reference/index.html"),
            )

    def test_non_guided_page_path_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            finalize_site_metadata.SiteMetadataError,
            "invalid guided page path",
        ):
            finalize_site_metadata.enhance_guided_copy_controls(
                guided_page(page_path="/other/"),
                PUBLIC_SITE_URL,
                Path("other/index.html"),
            )

    def test_normalization_enhances_guided_page_when_page_path_marker_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            page = site_root / "index.html"
            page.write_text(
                guided_page(page_path="/guided/", github_source=None),
                encoding="utf-8",
            )

            canonical_count, pwa_count = finalize_site_metadata.normalize_site_metadata(
                site_root,
                PUBLIC_SITE_URL,
            )

            self.assertEqual((canonical_count, pwa_count), (1, 1))
            rendered = page.read_text(encoding="utf-8")
            self.assertIn("Copy public URL", rendered)
            self.assertNotIn("Copy GitHub URL", rendered)
            self.assertIn("script-src 'self'", rendered)

    def test_copy_script_uses_clipboard_api_with_a_legacy_fallback(self) -> None:
        script = (ROOT / "assets/javascripts/guided-copy.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("navigator.clipboard.writeText", script)
        self.assertIn('document.execCommand("copy")', script)
        self.assertNotIn("onclick=", script.casefold())
        self.assertNotIn("innerHTML", script)


if __name__ == "__main__":
    unittest.main()
