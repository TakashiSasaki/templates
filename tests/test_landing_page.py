from __future__ import annotations

import re
import tomllib
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.md"
STYLESHEET = ROOT / "assets" / "stylesheets" / "extra.css"
IMAGES = ROOT / "assets" / "images"
EXPECTED_SVGS = {
    "landing-architecture.svg",
    "publication-pipeline.svg",
    "icon-skill.svg",
    "icon-policy.svg",
    "icon-webapp.svg",
}


class LandingPageTests(unittest.TestCase):
    def test_landing_page_exposes_all_primary_destinations(self) -> None:
        text = INDEX.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Templates documentation portal\n\n"))
        self.assertIn('class="portal-landing"', text)
        self.assertIn('id="choose-a-template"', text)
        for destination in ("skill/", "policy/", "webapp/", "repository-trees/"):
            self.assertIn(f'href="{destination}"', text)

    def test_landing_page_references_only_declared_svg_artwork(self) -> None:
        text = INDEX.read_text(encoding="utf-8")
        references = set(re.findall(r'src="images/([a-z0-9-]+\.svg)"', text))
        self.assertEqual(references, EXPECTED_SVGS)
        self.assertEqual(
            {path.name for path in IMAGES.glob("*.svg")},
            EXPECTED_SVGS,
        )

    def test_svg_artwork_is_responsive_and_contains_no_active_content(self) -> None:
        forbidden_elements = {"script", "foreignObject", "image", "iframe"}
        forbidden_reference = re.compile(r"(?:https?:|data:|javascript:)", re.IGNORECASE)

        for path in sorted(IMAGES.glob("*.svg")):
            with self.subTest(path=path.name):
                root = ET.parse(path).getroot()
                self.assertTrue(root.tag.endswith("svg"))
                self.assertIn("viewBox", root.attrib)
                self.assertNotIn("width", root.attrib)
                self.assertNotIn("height", root.attrib)
                for element in root.iter():
                    local_name = element.tag.rsplit("}", 1)[-1]
                    self.assertNotIn(local_name, forbidden_elements)
                    for name, value in element.attrib.items():
                        if name.rsplit("}", 1)[-1] in {"href", "src"}:
                            self.assertIsNone(forbidden_reference.match(value))

    def test_landing_styles_are_scoped_and_accessible(self) -> None:
        css = STYLESHEET.read_text(encoding="utf-8")
        for selector in (
            ".portal-landing",
            ".portal-hero",
            ".portal-card-grid",
            ".portal-publication",
            ".portal-tree-callout",
        ):
            self.assertIn(selector, css)
        self.assertIn(":focus-visible", css)
        self.assertIn("h1:has(+ .portal-landing)", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertNotIn("@import", css)

    def test_portal_metadata_matches_the_integrated_site(self) -> None:
        template = (ROOT / "zensical.template.toml").read_text(encoding="utf-8")
        parsed = tomllib.loads(template.replace("__GENERATED_NAV__", "[]"))
        project = parsed["project"]
        self.assertEqual(project["site_name"], "Templates Documentation Portal")
        self.assertEqual(project["site_url"], "https://templates.moukaeritai.work/")
        self.assertIn("skill, policy, and Web application", project["site_description"])


if __name__ == "__main__":
    unittest.main()
