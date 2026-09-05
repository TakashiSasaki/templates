from __future__ import annotations

import re
import tempfile
import tomllib
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "docs" / "landing.md"
STYLESHEET = ROOT / "assets" / "stylesheets" / "extra.css"
COVER_STYLESHEET = ROOT / "assets" / "stylesheets" / "landing-cover.css"
SHELL_STYLESHEET = ROOT / "assets" / "stylesheets" / "landing-shell.css"
MOBILE_STYLESHEET = ROOT / "assets" / "stylesheets" / "mobile-density.css"
TRANSLATION_STYLESHEET = ROOT / "assets" / "stylesheets" / "translation-reader.css"
IMAGES = ROOT / "assets" / "images"
EXPECTED_SVGS = {
    "landing-architecture.svg",
    "icon-skill.svg",
    "icon-policy.svg",
    "icon-web.svg",
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
    def test_graphical_cover_exposes_primary_destinations(self) -> None:
        text = LANDING.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Templates documentation portal\n\n"))
        self.assertIn('class="portal-landing portal-landing--cover"', text)
        self.assertIn('class="portal-cover"', text)
        self.assertNotIn('href="overview/"', text)
        self.assertIn(
            'class="portal-cover__button portal-cover__button--primary" href="web/"',
            text,
        )
        self.assertIn(
            'class="portal-cover__button portal-cover__button--secondary" href="playground/"',
            text,
        )
        self.assertEqual(text.count('class="portal-cover__button '), 3)
        for destination in (
            "web/",
            "playground/",
            "website/",
            "webapp/",
            "composition/use/skill-first-use-walkthrough/",
            "composition/",
            "capabilities/",
            "lifecycle/",
            "skill/",
            "policy/",
            "policy/getting-started/",
            "/glossary/",
            "/guided/",
            "repository-trees/",
            "files/",
        ):
            self.assertIn(f'href="{destination}"', text)
        self.assertIn("Browse by index.md", text)
        self.assertIn(">Source files</a>", text)
        self.assertIn('class="portal-artifact-grid"', text)
        self.assertIn('class="portal-artifact-card portal-artifact-card--skill"', text)
        self.assertIn('class="portal-artifact-card portal-artifact-card--webapp"', text)
        self.assertIn("Choose Website or Web application", text)
        self.assertNotIn("portal-artifact-card--policy", text)
        self.assertIn('class="portal-policy-panel"', text)
        self.assertIn("Independent task · Policy", text)

    def test_landing_page_references_only_declared_svg_artwork(self) -> None:
        text = LANDING.read_text(encoding="utf-8")
        references = set(
            re.findall(r'src="(?:\.\./)?images/([a-z0-9-]+\.svg)"', text)
        )
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

    def test_cover_styles_are_scoped_and_responsive(self) -> None:
        css = STYLESHEET.read_text(encoding="utf-8")
        cover_css = COVER_STYLESHEET.read_text(encoding="utf-8")
        shell_css = SHELL_STYLESHEET.read_text(encoding="utf-8")
        mobile_css = MOBILE_STYLESHEET.read_text(encoding="utf-8")
        translation_css = TRANSLATION_STYLESHEET.read_text(encoding="utf-8")
        self.assertIn(".portal-landing", css)
        for selector in (
            ".portal-landing--cover",
            ".portal-cover",
            ".portal-authority",
            ".portal-artifact-grid",
            ".portal-artifact-card",
            ".portal-policy-panel",
            ".portal-doc-nav",
            ".portal-doc-link",
            ".portal-guarantees",
        ):
            self.assertIn(selector, cover_css)
        self.assertIn(":focus-visible", cover_css)
        self.assertIn("h1:has(+ .portal-landing)", css)
        self.assertIn("container: portal / inline-size", css)
        self.assertIn("@container portal (max-width: 52rem)", cover_css)
        self.assertIn("@container portal (max-width: 34rem)", cover_css)
        self.assertIn("prefers-reduced-motion", cover_css)
        self.assertNotIn("@import", cover_css)

        self.assertIn("@media screen and (min-width: 60rem)", shell_css)
        self.assertIn(":has(.portal-landing--cover)", shell_css)
        self.assertIn("> .md-sidebar", shell_css)
        self.assertNotIn("@import", shell_css)

        mobile_query = "@media screen and (max-width: 44.984375em)"
        self.assertEqual(mobile_css.count(mobile_query), 1)
        unscoped_prefix = re.sub(
            r"/\*.*?\*/",
            "",
            mobile_css[: mobile_css.index(mobile_query)],
            flags=re.DOTALL,
        )
        self.assertNotIn("{", unscoped_prefix)
        for selector in (
            ".md-main__inner",
            ".md-path",
            ".md-content__inner",
            ".md-typeset h1",
            ".md-typeset h2",
            ".md-typeset h3",
            ".md-typeset blockquote",
            ".md-typeset table:not([class])",
            ".md-typeset table:not([class]) th",
            ".md-typeset table:not([class]) td",
            ".md-typeset table:not([class]) code",
            ".portal-cover",
            ".portal-cover__lead",
            ".portal-cover__button",
            ".portal-authority",
            ".portal-artifact-card",
            ".portal-policy-panel",
            ".portal-doc-link",
            ".portal-guarantees article",
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
                "stylesheets/freshness-status.css",
                "stylesheets/composition-playground.css",
            ],
        )
        self.assertEqual(
            parsed["project"]["extra_javascript"],
            [
                "javascripts/repository-tree-viewer.js",
                "javascripts/pwa.js",
                "javascripts/reader-navigation.js",
                "javascripts/search-history.js",
                "javascripts/glossary-inline.js",
                "javascripts/composition-playground.js",
                "javascripts/composition-playground-explain.js",
            ],
        )

    def test_portal_metadata_matches_the_integrated_site(self) -> None:
        template = (ROOT / "zensical.template.toml").read_text(encoding="utf-8")
        parsed = tomllib.loads(template.replace("__GENERATED_NAV__", "[]"))
        project = parsed["project"]
        self.assertEqual(project["site_name"], "Templates Documentation Portal")
        self.assertEqual(project["site_url"], "https://templates.moukaeritai.work/")
        self.assertIn("Website, Web application, Agent Skill", project["site_description"])
        self.assertIn("coding-agent Policy", project["site_description"])


if __name__ == "__main__":
    unittest.main()
