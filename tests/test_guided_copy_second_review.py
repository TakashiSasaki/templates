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


CSP_PREFIX = '<meta http-equiv="Content-Security-Policy" content="'
PAGE = Path("guided/skill/index.html")
PUBLIC_SITE_URL = "https://templates.moukaeritai.work/"


def guided_source(*, body_close: str = "</body>", page_markers: int = 1) -> str:
    marker = (
        '<p class="page-path"><span class="page-path-label">Page path:</span> '
        '<code>/guided/skill/</code></p>'
    )
    return (
        "<html><head>"
        + CSP_PREFIX
        + "default-src 'none'"
        + '"></head><body>'
        + marker * page_markers
        + body_close
        + "</html>"
    )


class GuidedCopySecondReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        chrome = load_site_chrome_locales(SITE_CHROME_LOCALES)
        cls.copy_strings = guided_copy_strings(chrome, "en")

    def test_csp_allows_existing_script_src_self(self) -> None:
        source = CSP_PREFIX + "default-src 'none'; script-src 'self'" + '">'
        rendered = finalize_site_metadata.allow_guided_copy_script(source, PAGE)
        self.assertEqual(rendered.count("script-src 'self'"), 1)

    def test_rejects_multiple_page_path_markers(self) -> None:
        with self.assertRaisesRegex(
            finalize_site_metadata.SiteMetadataError,
            "multiple guided page path markers",
        ):
            finalize_site_metadata.enhance_guided_copy_controls(
                guided_source(page_markers=2),
                PUBLIC_SITE_URL,
                PAGE,
                self.copy_strings,
            )

    def test_rejects_invalid_body_tag_count(self) -> None:
        for body_close in ("", "</body></body>"):
            with self.subTest(body_close=body_close):
                with self.assertRaisesRegex(
                    finalize_site_metadata.SiteMetadataError,
                    "expected exactly one closing body tag",
                ):
                    finalize_site_metadata.enhance_guided_copy_controls(
                        guided_source(body_close=body_close),
                        PUBLIC_SITE_URL,
                        PAGE,
                        self.copy_strings,
                    )

    def test_status_timer_is_replaced_after_async_copy_finishes(self) -> None:
        script = (ROOT / "assets/javascripts/guided-copy.js").read_text(encoding="utf-8")
        finally_block = script.split("} finally {", 1)[1]
        self.assertLess(
            finally_block.index("window.clearTimeout(existingTimeout)"),
            finally_block.index("window.setTimeout"),
        )
        pre_finally = script.split("} finally {", 1)[0]
        self.assertNotIn("window.clearTimeout(existingTimeout)", pre_finally)


if __name__ == "__main__":
    unittest.main()
