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


if __name__ == "__main__":
    unittest.main()
