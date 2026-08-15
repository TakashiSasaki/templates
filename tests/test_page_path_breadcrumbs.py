from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import finalize_site_metadata  # noqa: E402
from finalize_guided_locales import (  # noqa: E402
    enhance_localized_guided_copy_controls,
)


CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; manifest-src 'self'; "
    "base-uri 'none'; form-action 'none'"
)
PUBLIC_SITE_URL = "https://templates.moukaeritai.work/"


def guided_page(page_path: str, *, label: str = "Page path:") -> str:
    return (
        "<!doctype html><html><head>"
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
        "<title>Guided</title></head><body><main>"
        f'<p class="page-path"><span class="page-path-label">{label}</span> '
        f"<code>{page_path}</code></p>"
        "</main></body></html>"
    )


class PagePathBreadcrumbTests(unittest.TestCase):
    def test_root_is_home_link_without_route_declaration(self) -> None:
        rendered = finalize_site_metadata.render_page_path_breadcrumb(
            "/guided/",
            {"/guided/"},
        )

        self.assertTrue(
            rendered.startswith(
                '<a class="page-path-home" href="/" aria-label="Home">/</a><wbr>'
            )
        )
        self.assertNotIn('class="page-path-separator" aria-hidden="true">/</span><wbr>guided', rendered)

    def test_only_generated_route_prefixes_become_links(self) -> None:
        with tempfile.TemporaryDirectory(prefix="page-path-") as directory:
            root = Path(directory)
            pages = {
                "index.html": "/guided/",
                "skill/index.html": "/guided/skill/",
                "skill/docs/reference/index.html": "/guided/skill/docs/reference/",
            }
            for relative, route in pages.items():
                page = root / relative
                page.parent.mkdir(parents=True, exist_ok=True)
                page.write_text(guided_page(route), encoding="utf-8")

            finalize_site_metadata.normalize_site_metadata(root, PUBLIC_SITE_URL)
            rendered = (root / "skill/docs/reference/index.html").read_text(
                encoding="utf-8"
            )

            self.assertIn(
                '<a class="page-path-home" href="/" aria-label="Home">/</a><wbr>',
                rendered,
            )
            self.assertIn(
                '<a class="page-path-segment" href="/guided/">guided</a>',
                rendered,
            )
            self.assertIn(
                '<a class="page-path-segment" href="/guided/skill/">skill</a>',
                rendered,
            )
            self.assertNotIn('href="/guided/skill/docs/"', rendered)
            self.assertIn(
                '<span class="page-path-segment">docs</span>',
                rendered,
            )
            self.assertIn(
                '<span class="page-path-segment" aria-current="page">reference</span>',
                rendered,
            )
            self.assertIn('<nav class="page-path" aria-label="Page path">', rendered)
            self.assertIn("<wbr>", rendered)

    def test_repository_root_namespace_gap_stays_plain_text(self) -> None:
        with tempfile.TemporaryDirectory(prefix="page-path-") as directory:
            root = Path(directory)
            landing = root / "index.html"
            repository_root = root / "_repository-root/skill/index.html"
            repository_root.parent.mkdir(parents=True)
            landing.write_text(guided_page("/guided/"), encoding="utf-8")
            repository_root.write_text(
                guided_page("/guided/_repository-root/skill/"),
                encoding="utf-8",
            )

            finalize_site_metadata.normalize_site_metadata(root, PUBLIC_SITE_URL)
            rendered = repository_root.read_text(encoding="utf-8")

            self.assertIn('href="/" aria-label="Home"', rendered)
            self.assertIn('href="/guided/"', rendered)
            self.assertNotIn('href="/guided/_repository-root/"', rendered)
            self.assertIn(
                '<span class="page-path-segment">_repository-root</span>',
                rendered,
            )
            self.assertIn(
                '<span class="page-path-segment" aria-current="page">skill</span>',
                rendered,
            )

    def test_localized_prefixes_use_only_existing_localized_routes(self) -> None:
        rendered = enhance_localized_guided_copy_controls(
            guided_page(
                "/ja/guided/policy/",
                label="ページパス:",
            ),
            PUBLIC_SITE_URL,
            "ja",
            Path("ja/guided/policy/index.html"),
            {
                "/ja/guided/",
                "/ja/guided/policy/",
            },
        )

        self.assertIn(
            '<a class="page-path-home" href="/" aria-label="Home">/</a><wbr>',
            rendered,
        )
        self.assertNotIn('href="/ja/"', rendered)
        self.assertIn(
            '<span class="page-path-segment">ja</span>',
            rendered,
        )
        self.assertIn(
            '<a class="page-path-segment" href="/ja/guided/">guided</a>',
            rendered,
        )
        self.assertIn(
            '<span class="page-path-segment" aria-current="page">policy</span>',
            rendered,
        )
        self.assertIn(
            '<nav class="page-path" aria-label="ページパス:">',
            rendered,
        )

    def test_duplicate_declared_routes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="page-path-") as directory:
            root = Path(directory)
            first = root / "one/index.html"
            second = root / "two/index.html"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_text(guided_page("/guided/duplicate/"), encoding="utf-8")
            second.write_text(guided_page("/guided/duplicate/"), encoding="utf-8")

            with self.assertRaisesRegex(
                finalize_site_metadata.SiteMetadataError,
                "also declared by",
            ):
                finalize_site_metadata.normalize_site_metadata(root, PUBLIC_SITE_URL)


if __name__ == "__main__":
    unittest.main()