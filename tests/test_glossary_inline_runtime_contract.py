from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GlossaryInlineRuntimeContractTests(unittest.TestCase):
    def test_runtime_promotes_fallback_links_to_native_buttons(self) -> None:
        script = (ROOT / "assets/javascripts/glossary-inline.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('document.createElement("button")', script)
        self.assertIn('trigger.type = "button"', script)
        self.assertIn('trigger.dataset.glossaryHref', script)
        self.assertIn('trigger.setAttribute("aria-haspopup", "dialog")', script)
        self.assertIn('trigger.setAttribute("aria-expanded", "false")', script)
        self.assertIn("enhanceGlossaryLinks(document)", script)

    def test_runtime_preserves_inline_markup_when_promoting_links(self) -> None:
        script = (ROOT / "assets/javascripts/glossary-inline.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("while (link.firstChild)", script)
        self.assertIn("trigger.appendChild(link.firstChild)", script)
        self.assertNotIn("trigger.textContent = link.textContent", script)

    def test_runtime_keeps_explicit_fallback_without_implicit_navigation(self) -> None:
        script = (ROOT / "assets/javascripts/glossary-inline.js").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("window.location.assign", script)
        self.assertNotIn("window.location =", script)
        self.assertIn("function restoreFallbackLink(trigger)", script)
        self.assertIn('link.setAttribute("href", fallbackHref(trigger));', script)
        self.assertIn("restoreFallbackLink(trigger);", script)
        self.assertIn("strings.definition_load_failed", script)
        self.assertIn("strings.definition_not_found", script)
        self.assertIn("strings.open_in_glossary", script)

    def test_glossary_chrome_is_resolved_from_shared_locale_registry(self) -> None:
        script = (ROOT / "assets/javascripts/glossary-inline.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('const SITE_CHROME_LOCALES_URL = "/site-chrome-locales.json";', script)
        self.assertIn("function parseGlossaryChrome(value)", script)
        self.assertIn("function glossaryStrings(model, language)", script)
        self.assertIn("model.locales.get(primary)", script)
        self.assertIn("model.locales.get(model.canonicalLanguage)", script)
        self.assertIn("document.documentElement?.lang", script)
        for literal in (
            "Close definition",
            "Open in Glossary",
            "Definition could not be loaded.",
            "Definition could not be found.",
            "Saved glossary data · latest version not verified.",
        ):
            self.assertNotIn(literal, script)

    def test_glossary_controls_have_non_navigation_visual_semantics(self) -> None:
        stylesheet = (ROOT / "assets/stylesheets/glossary-inline.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("cursor: help", stylesheet)
        self.assertIn("button.glossary-term", stylesheet)
        self.assertIn("appearance: none", stylesheet)
        self.assertIn("background: none", stylesheet)
        self.assertIn("font: inherit", stylesheet)

    def test_glossary_dialog_maintains_progressive_background_fallback(self) -> None:
        stylesheet = (ROOT / "assets/stylesheets/glossary-inline.css").read_text(
            encoding="utf-8"
        )
        dialog_rule = stylesheet.split(".glossary-inline-dialog {", 1)[1].split("}", 1)[0]
        fallback = "background: var(--md-default-bg-color, Canvas);"
        tint = "background: color-mix("
        self.assertIn(fallback, dialog_rule)
        self.assertIn(tint, dialog_rule)
        self.assertLess(dialog_rule.index(fallback), dialog_rule.index(tint))
        self.assertIn("var(--md-default-bg-color, Canvas)", dialog_rule)
        self.assertNotIn("var(--md-default-bg-color, #fff)", dialog_rule)

    def test_glossary_dialog_readability_metrics_and_tint_are_explicit(self) -> None:
        stylesheet = (ROOT / "assets/stylesheets/glossary-inline.css").read_text(
            encoding="utf-8"
        )
        dialog_rule = stylesheet.split(".glossary-inline-dialog {", 1)[1].split("}", 1)[0]
        definition_rule = stylesheet.split(
            ".glossary-inline-dialog__definition {", 1
        )[1].split("}", 1)[0]
        self.assertIn("var(--md-primary-fg-color, #3f51b5) 30%", dialog_rule)
        self.assertIn("var(--md-primary-fg-color, #3f51b5) 14%", dialog_rule)
        self.assertIn("font-size: 0.9rem;", definition_rule)
        self.assertIn("line-height: 1.65;", definition_rule)


if __name__ == "__main__":
    unittest.main()
