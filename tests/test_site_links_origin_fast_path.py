from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_site_links  # noqa: E402


class SiteLinkOriginFastPathTests(unittest.TestCase):
    def _fixture(self, href: str) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        site_root = root / "site"
        site_root.mkdir()
        (site_root / "index.html").write_text(
            f'<html><body><main><a href="{href}">target</a></main></body></html>',
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
        return temporary, site_root, config

    def test_authored_local_link_reuses_validated_site_origin(self) -> None:
        temporary, site_root, config = self._fixture("target/#ok")
        with temporary:
            original = validate_site_links.normalized_origin
            descriptions: list[str] = []

            def record_origin(parts, description):
                descriptions.append(description)
                return original(parts, description)

            with mock.patch.object(
                validate_site_links,
                "normalized_origin",
                side_effect=record_origin,
            ):
                pages, links, diagnostics = validate_site_links.validate_site(
                    site_root, config
                )

            self.assertEqual((2, 1, []), (pages, links, diagnostics))
            self.assertEqual(
                ["project.site_url", "project.site_url"],
                descriptions,
                "authored-local links should inherit the already validated Site origin",
            )

    def test_external_network_path_still_normalizes_resolved_origin(self) -> None:
        temporary, site_root, config = self._fixture("//other.example/target/")
        with temporary:
            original = validate_site_links.normalized_origin
            descriptions: list[str] = []

            def record_origin(parts, description):
                descriptions.append(description)
                return original(parts, description)

            with mock.patch.object(
                validate_site_links,
                "normalized_origin",
                side_effect=record_origin,
            ):
                pages, links, diagnostics = validate_site_links.validate_site(
                    site_root, config
                )

            self.assertEqual((2, 0, []), (pages, links, diagnostics))
            link_descriptions = [
                description for description in descriptions if description != "project.site_url"
            ]
            self.assertEqual(1, len(link_descriptions))
            self.assertIn("//other.example/target/", link_descriptions[0])

    def test_same_scheme_shorthand_uses_inherited_origin_fast_path(self) -> None:
        temporary, site_root, config = self._fixture("https:target/#ok")
        with temporary:
            original = validate_site_links.normalized_origin
            descriptions: list[str] = []

            def record_origin(parts, description):
                descriptions.append(description)
                return original(parts, description)

            with mock.patch.object(
                validate_site_links,
                "normalized_origin",
                side_effect=record_origin,
            ):
                pages, links, diagnostics = validate_site_links.validate_site(
                    site_root, config
                )

            self.assertEqual((2, 1, []), (pages, links, diagnostics))
            self.assertEqual(["project.site_url", "project.site_url"], descriptions)


if __name__ == "__main__":
    unittest.main()
