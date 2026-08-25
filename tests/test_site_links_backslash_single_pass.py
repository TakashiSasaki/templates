from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_site_links  # noqa: E402


class SiteLinkBackslashSinglePassTests(unittest.TestCase):
    def test_validate_site_normalizes_each_link_backslash_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site_root = root / "site"
            site_root.mkdir()
            (site_root / "index.html").write_text(
                '<html><body><main><a href="target\\#ok">target</a></main></body></html>',
                encoding="utf-8",
            )
            target = site_root / "target"
            target.mkdir()
            (target / "index.html").write_text(
                '<html><body><main><h1 id="ok">Target</h1></main></body></html>',
                encoding="utf-8",
            )
            config = root / "zensical.toml"
            config.write_text(
                '[project]\nsite_url = "https://example.test/"\n',
                encoding="utf-8",
            )

            original = validate_site_links.normalize_special_url_backslashes
            calls: list[str] = []

            def record(value: str) -> str:
                calls.append(value)
                return original(value)

            with mock.patch.object(
                validate_site_links,
                "normalize_special_url_backslashes",
                side_effect=record,
            ):
                pages, links, diagnostics = validate_site_links.validate_site(
                    site_root, config
                )

            self.assertEqual((2, 1, []), (pages, links, diagnostics))
            self.assertEqual(["target\\#ok"], calls)

    def test_validate_site_parses_each_source_url_once_for_multiple_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site_root = root / "site"
            site_root.mkdir()
            (site_root / "index.html").write_text(
                "<html><body><main><p>Home</p></main></body></html>",
                encoding="utf-8",
            )
            guide = site_root / "guide"
            guide.mkdir()
            (guide / "index.html").write_text(
                '<html><body><main>'
                '<a href="../target/#one">one</a>'
                '<a href="../target/#two">two</a>'
                "</main></body></html>",
                encoding="utf-8",
            )
            target = site_root / "target"
            target.mkdir()
            (target / "index.html").write_text(
                '<html><body><main><h1 id="one">One</h1><h2 id="two">Two</h2></main></body></html>',
                encoding="utf-8",
            )
            config = root / "zensical.toml"
            config.write_text(
                '[project]\nsite_url = "https://example.test/docs/"\n',
                encoding="utf-8",
            )

            original = validate_site_links.urlsplit
            calls: list[str] = []

            def record(value: str):
                calls.append(value)
                return original(value)

            with mock.patch.object(validate_site_links, "urlsplit", side_effect=record):
                pages, links, diagnostics = validate_site_links.validate_site(
                    site_root, config
                )

            self.assertEqual((3, 2, []), (pages, links, diagnostics))
            self.assertEqual(1, calls.count("https://example.test/docs/guide/"))

    def test_public_resolver_still_normalizes_raw_input(self) -> None:
        original = validate_site_links.normalize_special_url_backslashes
        calls: list[str] = []

        def record(value: str) -> str:
            calls.append(value)
            return original(value)

        with mock.patch.object(
            validate_site_links,
            "normalize_special_url_backslashes",
            side_effect=record,
        ):
            resolved, authored_local = validate_site_links.resolve_http_reference(
                "https://example.test/docs/index.html",
                "guide\\#details",
            )

        self.assertTrue(authored_local)
        self.assertEqual("/docs/guide/", resolved.path)
        self.assertEqual("details", resolved.fragment)
        self.assertEqual(["guide\\#details"], calls)


if __name__ == "__main__":
    unittest.main()
