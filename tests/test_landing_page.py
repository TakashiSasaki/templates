from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "docs/landing.md"
OVERVIEW = ROOT / "docs/portal-overview.md"
COVER_CSS = ROOT / "assets/stylesheets/landing-cover.css"
SHELL_CSS = ROOT / "assets/stylesheets/landing-shell.css"
MOBILE_CSS = ROOT / "assets/stylesheets/mobile-density.css"
TRANSLATION_CSS = ROOT / "assets/stylesheets/translation-reader.css"
COVER_SVG = ROOT / "assets/images/landing-cover.svg"
SITE_MANIFEST = ROOT / "site-manifest.json"
PUBLICATION_CATALOG = ROOT / "docs/publication-catalog.json"


class LandingPageTests(unittest.TestCase):
    def test_graphical_cover_exposes_primary_destinations_and_overview(self) -> None:
        text = LANDING.read_text(encoding="utf-8")

        self.assertIn("# Templates Documentation Portal", text)
        self.assertIn("landing-cover.svg", text)
        self.assertIn('class="portal-cover"', text)
        self.assertIn('class="portal-domain-grid"', text)
        self.assertIn('class="portal-cover-features"', text)
        self.assertIn('class="portal-cover__secondary" href="portal-overview/"', text)
        self.assertIn('class="portal-cover__tertiary" href="glossary/"', text)
        self.assertIn('class="portal-cover__tertiary" href="files/"', text)
        self.assertIn('class="portal-cover__tertiary" href="guided/"', text)
        for href in ("skill/", "policy/", "webapp/"):
            self.assertIn(f'href="{href}"', text)

        self.assertNotIn("## Repository trees", text)
        self.assertNotIn("## Scope", text)

    def test_overview_preserves_the_detailed_portal_explanation(self) -> None:
        text = OVERVIEW.read_text(encoding="utf-8")

        self.assertIn("# Portal overview", text)
        self.assertIn("## Integrated publications", text)
        self.assertIn("## Repository trees", text)
        self.assertIn("## Scope", text)
        self.assertIn("../repository-trees/", text)
        self.assertIn("../glossary/", text)
        self.assertIn("../files/", text)
        self.assertIn("../guided/", text)
        self.assertIn("https://templates.moukaeritai.work/", text)

    def test_landing_pages_reference_only_declared_svg_artwork(self) -> None:
        catalog = __import__("json").loads(PUBLICATION_CATALOG.read_text(encoding="utf-8"))
        assets = catalog["assets"]
        declared = {(entry["source"], entry["destination"]) for entry in assets}

        self.assertIn(("assets/images", "images"), declared)
        for source in (LANDING, OVERVIEW):
            text = source.read_text(encoding="utf-8")
            for match in re.findall(r"(?:src|href)=\"([^\"]+\.svg)\"", text):
                self.assertFalse(match.startswith("http"))
                self.assertFalse(match.startswith("//"))

    def test_svg_artwork_is_responsive_and_contains_no_active_content(self) -> None:
        root = ElementTree.fromstring(COVER_SVG.read_text(encoding="utf-8"))
        self.assertEqual(root.tag.rsplit("}", 1)[-1], "svg")
        self.assertIsNotNone(root.attrib.get("viewBox"))
        self.assertNotIn("width", root.attrib)
        self.assertNotIn("height", root.attrib)
        for node in root.iter():
            local = node.tag.rsplit("}", 1)[-1]
            self.assertNotEqual(local, "script")
            for name, value in node.attrib.items():
                self.assertFalse(name.lower().startswith("on"))
                if name.rsplit("}", 1)[-1] == "href":
                    self.assertFalse(value.startswith(("http:", "https:", "//")))

    def test_svg_validator_rejects_active_and_external_content(self) -> None:
        unsafe = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            '<script>alert(1)</script><image href="https://example.com/x.svg" />'
            "</svg>"
        )
        root = ElementTree.fromstring(unsafe)
        active = []
        external = []
        for node in root.iter():
            local = node.tag.rsplit("}", 1)[-1]
            if local == "script":
                active.append(local)
            for name, value in node.attrib.items():
                if name.lower().startswith("on"):
                    active.append(name)
                if name.rsplit("}", 1)[-1] == "href" and value.startswith(
                    ("http:", "https:", "//")
                ):
                    external.append(value)
        self.assertTrue(active)
        self.assertTrue(external)

    def test_portal_metadata_matches_the_integrated_site(self) -> None:
        template = (ROOT / "zensical.template.toml").read_text(encoding="utf-8")
        parsed = tomllib.loads(template.replace("__GENERATED_NAV__", "[]"))
        project = parsed["project"]

        self.assertEqual(project["site_name"], "Templates Documentation Portal")
        self.assertEqual(project["repo_name"], "TakashiSasaki/templates")
        self.assertEqual(project["site_url"], "https://templates.moukaeritai.work/")
        parsed_url = urlsplit(project["site_url"])
        self.assertEqual(parsed_url.scheme, "https")
        self.assertEqual(parsed_url.netloc, "templates.moukaeritai.work")
        self.assertEqual(parsed_url.path, "/")

    def test_cover_and_overview_styles_are_scoped_and_responsive(self) -> None:
        cover_css = COVER_CSS.read_text(encoding="utf-8")
        shell_css = SHELL_CSS.read_text(encoding="utf-8")
        mobile_css = MOBILE_CSS.read_text(encoding="utf-8")
        translation_css = TRANSLATION_CSS.read_text(encoding="utf-8")
        mobile_query = "@media (max-width: 700px)"

        for selector in (
            ".portal-cover",
            ".portal-cover__grid",
            ".portal-domain-grid",
            ".portal-cover-features",
        ):
            self.assertIn(selector, cover_css)
        self.assertIn(mobile_query, cover_css)
        self.assertNotIn("@import", cover_css)

        for selector in (
            ".portal-overview-lead",
            ".portal-overview-grid",
            ".portal-overview-card",
        ):
            self.assertIn(selector, shell_css)
        self.assertIn(mobile_query, shell_css)
        self.assertNotIn("@import", shell_css)

        for selector in (
            ".portal-cover__button",
            ".portal-domain-card",
            ".portal-cover-features article",
        ):
            self.assertIn(selector, mobile_css)
        self.assertIn("min-height: 48px", mobile_css)
        self.assertIn("overflow-x: auto", mobile_css)
        self.assertIn("overscroll-behavior-x: contain", mobile_css)
        self.assertIn("-webkit-overflow-scrolling: touch", mobile_css)
        self.assertIn("white-space: nowrap", mobile_css)
        self.assertIn("overflow-wrap: normal", mobile_css)
        self.assertIn("word-break: normal", mobile_css)
        self.assertNotIn("@import", mobile_css)

        self.assertIn(".translation-switcher", translation_css)
        self.assertIn(".translation-switcher__link", translation_css)
        self.assertIn(mobile_query, translation_css)
        self.assertNotIn("@import", translation_css)

        template = (ROOT / "zensical.template.toml").read_text(encoding="utf-8")
        parsed = tomllib.loads(template.replace("__GENERATED_NAV__", "[]"))
        self.assertEqual(
            parsed["project"]["extra_css"],
            [
                "stylesheets/extra.css",
                "stylesheets/landing-cover.css",
                "stylesheets/landing-shell.css",
                "stylesheets/mobile-density.css",
                "stylesheets/translation-reader.css",
                "stylesheets/glossary-inline.css",
            ],
        )


if __name__ == "__main__":
    unittest.main()
