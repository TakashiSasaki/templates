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

    def test_runtime_never_uses_implicit_navigation_after_enhancement(self) -> None:
        script = (ROOT / "assets/javascripts/glossary-inline.js").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("window.location.assign", script)
        self.assertIn("Definition could not be loaded.", script)
        self.assertIn("Definition could not be found.", script)
        self.assertIn("Open in Glossary", script)

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

        self.assertIn("var(--md-primary-fg-color, #3f51b5) 14%", dialog_rule)
        self.assertIn("font-size: 0.9rem;", definition_rule)
        self.assertIn("line-height: 1.65;", definition_rule)


if __name__ == "__main__":
    unittest.main()
