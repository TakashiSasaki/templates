from __future__ import annotations

import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_URL_BOUNDARY_CHECKER = ROOT / "scripts/check_public_url_boundary.py"
sys.path.insert(0, str(ROOT / "scripts"))

import finalize_site_metadata  # noqa: E402
import prepare_site_metadata  # noqa: E402


CANONICAL_URL = "https://templates.moukaeritai.work/"


class DeploymentNoticeTests(unittest.TestCase):
    def test_deployment_timestamp_becomes_footer_notice(self) -> None:
        self.assertEqual(
            "Deployment time: 2026-08-04 18:08:00 JST",
            prepare_site_metadata.deployment_notice("2026-08-04 18:08:00 JST"),
        )

    def test_empty_timestamp_marks_non_deploying_build(self) -> None:
        self.assertEqual(
            "Preview build (not deployed)",
            prepare_site_metadata.deployment_notice(""),
        )

    def test_invalid_timestamp_is_rejected(self) -> None:
        for value in (
            "2026-08-04T09:08:00Z",
            "2026-8-4 18:08 JST",
            "2026-08-04 18:08:00 UTC",
            "<script>alert(1)</script>",
        ):
            with self.subTest(value=value):
                with self.assertRaises(prepare_site_metadata.SiteMetadataError):
                    prepare_site_metadata.deployment_notice(value)

    def test_prepared_config_contains_footer_notice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_file = Path(temporary_directory) / "zensical.toml"
            config_file.write_text(
                "[project]\n"
                'site_name = "Test"\n'
                f'site_url = "{CANONICAL_URL}"\n'
                "\n[project.theme]\nfont = false\n",
                encoding="utf-8",
            )

            notice = prepare_site_metadata.prepare_config(
                config_file,
                "2026-08-04 18:08:00 JST",
                CANONICAL_URL,
            )

            self.assertEqual("Deployment time: 2026-08-04 18:08:00 JST", notice)
            config = tomllib.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(notice, config["project"]["copyright"])
            self.assertEqual(CANONICAL_URL, config["project"]["site_url"])


class CanonicalMetadataTests(unittest.TestCase):
    def test_every_generated_page_uses_the_public_site_canonical_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            nested = site_root / "guide"
            nested.mkdir()
            (site_root / "index.html").write_text(
                "<html><head>"
                '<link rel="canonical" href="https://old.example/root">'
                "</head><body>home</body></html>",
                encoding="utf-8",
            )
            (nested / "index.html").write_text(
                "<html><head>"
                "<link href='https://old.example/guide/' rel='alternate canonical'>"
                "</head><body>guide</body></html>",
                encoding="utf-8",
            )

            normalized = finalize_site_metadata.normalize_canonical_links(
                site_root,
                CANONICAL_URL,
            )

            self.assertEqual(2, normalized)
            for path in (site_root / "index.html", nested / "index.html"):
                html = path.read_text(encoding="utf-8")
                self.assertIn(f'href="{CANONICAL_URL}"', html)
                self.assertNotIn("https://old.example", html)

    def test_missing_canonical_link_is_inserted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            page = site_root / "404.html"
            page.write_text(
                "<html><head><title>Not found</title></head><body></body></html>",
                encoding="utf-8",
            )

            normalized = finalize_site_metadata.normalize_canonical_links(
                site_root,
                CANONICAL_URL,
            )

            self.assertEqual(1, normalized)
            html = page.read_text(encoding="utf-8")
            self.assertIn(
                f'<link rel="canonical" href="{CANONICAL_URL}">',
                html,
            )

    def test_duplicate_canonical_links_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            (site_root / "index.html").write_text(
                "<html><head>"
                '<link rel="canonical" href="https://one.example/">'
                '<link rel="canonical" href="https://two.example/">'
                "</head><body></body></html>",
                encoding="utf-8",
            )
            with self.assertRaises(finalize_site_metadata.SiteMetadataError):
                finalize_site_metadata.normalize_canonical_links(
                    site_root,
                    CANONICAL_URL,
                )


class PublicUrlContractTests(unittest.TestCase):
    def test_custom_domain_is_an_https_root_site(self) -> None:
        parsed = urlsplit(CANONICAL_URL)

        self.assertEqual("https", parsed.scheme)
        self.assertEqual("templates.moukaeritai.work", parsed.netloc)
        self.assertEqual("/", parsed.path)
        self.assertFalse(parsed.query)
        self.assertFalse(parsed.fragment)


class DeploymentWorkflowWiringTests(unittest.TestCase):
    pass

if __name__ == "__main__":
    unittest.main()
