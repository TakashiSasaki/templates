from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReaderNavigationRuntimeContractTests(unittest.TestCase):
    def script(self) -> str:
        return (ROOT / "assets/javascripts/reader-navigation.js").read_text(
            encoding="utf-8"
        )

    def test_runtime_is_loaded_by_the_site_template(self) -> None:
        template = (ROOT / "zensical.template.toml").read_text(encoding="utf-8")
        self.assertIn('"javascripts/reader-navigation.js"', template)

    def test_runtime_only_enhances_the_primary_reader_navigation(self) -> None:
        script = self.script()
        self.assertIn('const PRIMARY_NAV_SELECTOR = "nav.md-nav--primary"', script)
        self.assertIn("document.querySelectorAll(PRIMARY_NAV_SELECTOR)", script)
        self.assertIn('nav.querySelectorAll(".md-ellipsis")', script)
        self.assertIn('nav.querySelectorAll("a.md-nav__link[href]")', script)
        self.assertNotIn('document.querySelectorAll(".md-ellipsis")', script)

    def test_runtime_uses_only_server_generated_current_translation_routes(self) -> None:
        script = self.script()
        self.assertIn("const localizedPath = routes[target.pathname]", script)
        self.assertIn("target.origin !== window.location.origin", script)
        self.assertNotIn('`/ja/${', script)
        self.assertNotIn('"/ja/" +', script)

    def test_runtime_restores_canonical_navigation_before_locale_changes(self) -> None:
        script = self.script()
        self.assertIn("data-reader-nav-canonical-label", script)
        self.assertIn("data-reader-nav-canonical-href", script)
        self.assertIn("restoreNavigation(nav);", script)
        self.assertIn('link.setAttribute("href", canonicalHref)', script)

    def test_runtime_tracks_instant_navigation_and_fails_open_to_canonical_ui(self) -> None:
        script = self.script()
        self.assertIn("window.document$", script)
        self.assertIn("navigationDocument.subscribe", script)
        self.assertIn('cache: "no-cache"', script)
        self.assertIn("Reader navigation localization unavailable", script)
        self.assertNotIn("window.location.assign", script)


if __name__ == "__main__":
    unittest.main()
