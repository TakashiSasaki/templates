from __future__ import annotations

import unittest
from pathlib import Path

from scripts.finalize_glossary_annotations import RUNTIME_SCRIPT, RUNTIME_STYLE


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "assets/javascripts/glossary-inline.js"
CSS = ROOT / "assets/stylesheets/glossary-inline.css"
TEMPLATE = ROOT / "zensical.template.toml"


class GlossaryInlineAssetTests(unittest.TestCase):
    def test_runtime_fetch_and_dialog_creation_are_activation_lazy(self) -> None:
        source = JS.read_text(encoding="utf-8")

        self.assertEqual(source.count("fetch(GLOSSARY_URL"), 1)
        self.assertEqual(source.count("loadGlossary("), 2)
        self.assertEqual(source.count("ensureDialog("), 2)
        self.assertIn("terms = await loadGlossary();", source)
        self.assertIn("const panel = ensureDialog();", source)
        self.assertIn("void openDefinition(link);", source)
        self.assertNotIn("DOMContentLoaded", source)
        self.assertNotIn("requestIdleCallback", source)

    def test_failed_fetch_can_retry_on_later_activation(self) -> None:
        source = JS.read_text(encoding="utf-8")

        self.assertIn("glossaryPromise = undefined;", source)
        self.assertIn("throw error;", source)

    def test_runtime_preserves_link_fallbacks_and_modified_clicks(self) -> None:
        source = JS.read_text(encoding="utf-8")

        self.assertGreaterEqual(source.count("window.location.assign(link.href);"), 3)
        for modifier in ("event.metaKey", "event.ctrlKey", "event.shiftKey", "event.altKey"):
            self.assertIn(modifier, source)
        self.assertIn('event.key !== "Escape"', source)
        self.assertIn('dialog.setAttribute("aria-labelledby"', source)
        self.assertIn('dialog.setAttribute("aria-describedby"', source)
        self.assertIn("restore.focus({ preventScroll: true })", source)

    def test_runtime_guards_navigation_races_and_active_link_containment(self) -> None:
        source = JS.read_text(encoding="utf-8")

        self.assertIn("let pendingLink;", source)
        self.assertIn("pendingLink = link;", source)
        self.assertGreaterEqual(source.count("pendingLink !== link"), 2)
        self.assertGreaterEqual(source.count("!link.isConnected"), 2)
        self.assertIn("!pendingLink.contains(target)", source)
        self.assertIn("!activeLink.contains(target)", source)

    def test_detached_active_link_closes_dialog_after_instant_navigation(self) -> None:
        source = JS.read_text(encoding="utf-8")

        self.assertIn("function closeDetachedDialog()", source)
        self.assertIn("activeLink && !activeLink.isConnected", source)
        self.assertIn("navigationObserver = new MutationObserver(closeDetachedDialog);", source)
        self.assertIn("navigationObserver.observe(document.body", source)
        self.assertIn("childList: true", source)
        self.assertIn("subtree: true", source)

    def test_escape_cancels_pending_open_and_pointer_dismissal_does_not_restore_focus(self) -> None:
        source = JS.read_text(encoding="utf-8")

        self.assertIn("let pointerDismissal = false;", source)
        self.assertIn("pointerDismissal = true;", source)
        self.assertIn("!pointerDismissal", source)
        self.assertIn("pendingLink = null;", source)

    def test_open_dialog_repositions_after_viewport_and_scroll_changes(self) -> None:
        source = JS.read_text(encoding="utf-8")

        self.assertIn("function repositionOpenDialog()", source)
        self.assertIn("positionDialog(activeLink, dialog);", source)
        self.assertIn('window.addEventListener("resize", repositionOpenDialog);', source)
        self.assertIn('document.addEventListener("scroll", repositionOpenDialog, {', source)
        self.assertIn("capture: true", source)
        self.assertIn("passive: true", source)

    def test_explanation_metadata_and_provider_labels_follow_glossary_contract(self) -> None:
        source = JS.read_text(encoding="utf-8")

        self.assertIn('term.origin === "repository" && typeof term.definition === "string"', source)
        self.assertIn('typeof term.summary === "string"', source)
        self.assertIn("return term.definition;", source)
        self.assertIn("return term.summary;", source)
        self.assertIn('site: "Site"', source)
        self.assertIn('skill: "Skill"', source)
        self.assertIn('policy: "Policy"', source)
        self.assertIn('webapp: "Webapp"', source)
        self.assertIn("`External term · curated by ${owner}`", source)
        self.assertIn("`Templates-defined · ${owner}`", source)

    def test_annotation_style_does_not_change_text_metrics(self) -> None:
        source = CSS.read_text(encoding="utf-8")
        annotation_rule = source.split(".glossary-term {", 1)[1].split("}", 1)[0]

        self.assertIn("text-decoration", annotation_rule)
        self.assertNotIn("font-size", annotation_rule)
        self.assertNotIn("font-weight", annotation_rule)
        self.assertNotIn("line-height", annotation_rule)
        self.assertNotIn("padding", annotation_rule)
        self.assertNotIn("margin", annotation_rule)

    def test_runtime_paths_match_published_assets(self) -> None:
        self.assertEqual(
            RUNTIME_SCRIPT,
            '<script src="/javascripts/glossary-inline.js" defer></script>',
        )
        self.assertEqual(
            RUNTIME_STYLE,
            '<link rel="stylesheet" href="/stylesheets/glossary-inline.css">',
        )
        self.assertTrue(JS.is_file())
        self.assertTrue(CSS.is_file())

    def test_runtime_assets_are_global_for_instant_navigation_but_data_remains_lazy(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('"stylesheets/glossary-inline.css"', template)
        self.assertIn('"javascripts/glossary-inline.js"', template)
        self.assertIn('"navigation.instant"', template)
        self.assertNotIn("/glossary/index.json", template)


if __name__ == "__main__":
    unittest.main()
