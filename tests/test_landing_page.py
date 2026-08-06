from __future__ import annotations

import re
import tempfile
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
FORBIDDEN_SVG_ELEMENTS = {
    "animate",
    "animateMotion",
    "animateTransform",
    "foreignObject",
    "iframe",
    "image",
    "script",
    "set",
    "style",
}
EXTERNAL_REFERENCE = re.compile(
    r"(?:https?|data|javascript|vbscript|file):|//",
    re.IGNORECASE,
)
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)


def validate_static_svg(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    if re.search(r"<!DOCTYPE|<!ENTITY|<\?xml-stylesheet\b", raw, re.IGNORECASE):
        raise ValueError("SVG must not declare external XML resources")

    root = ET.fromstring(raw)
    if not root.tag.endswith("svg"):
        raise ValueError("root element must be svg")
    if "viewBox" not in root.attrib:
        raise ValueError("SVG must define a viewBox")
    if "width" in root.attrib or "height" in root.attrib:
        raise ValueError("SVG root must remain responsive")

    for element in root.iter():
        element_name = element.tag.rsplit("}", 1)[-1]
        if element_name in FORBIDDEN_SVG_ELEMENTS:
            raise ValueError(f"forbidden SVG element: {element_name}")

        for qualified_name, value in element.attrib.items():
            attribute_name = qualified_name.rsplit("}", 1)[-1]
            lowered_name = attribute_name.casefold()
            if lowered_name.startswith("on") or lowered_name == "style":
                raise ValueError(f"forbidden SVG attribute: {attribute_name}")
            if EXTERNAL_REFERENCE.search(value):
                raise ValueError(f"external SVG reference: {value}")
            if lowered_name in {"href", "src"} and not value.startswith("#"):
                raise ValueError(f"non-fragment SVG reference: {value}")
            for match in CSS_URL.finditer(value):
                target = match.group(2).strip()
                if not target.startswith("#"):
                    raise ValueError(f"external CSS URL in SVG: {target}")


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
        for path in sorted(IMAGES.glob("*.svg")):
            with self.subTest(path=path.name):
                validate_static_svg(path)

    def test_svg_validator_rejects_active_and_external_content(self) -> None:
        unsafe_documents = {
            "event-handler.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1" onload="alert(1)"/>',
            "external-paint.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><rect fill="url(https://example.invalid/paint)"/></svg>',
            "style-element.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><style>@import url(https://example.invalid/a.css);</style></svg>',
            "style-attribute.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><rect style="fill:url(//example.invalid/paint)"/></svg>',
            "data-image.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><image href="data:image/png;base64,AA=="/></svg>',
            "external-entity.svg": '<!DOCTYPE svg [<!ENTITY ext SYSTEM "https://example.invalid/x">]><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>',
        }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in unsafe_documents.items():
                with self.subTest(name=name):
                    path = root / name
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        validate_static_svg(path)

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
        self.assertIn("container: portal / inline-size", css)
        self.assertIn("@container portal (max-width: 42rem)", css)
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
