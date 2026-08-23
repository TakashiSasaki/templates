from __future__ import annotations

import tomllib
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
        self.assertEqual(source.count("fetch(SITE_CHROME_LOCALES_URL"), 1)
        self.assertEqual(source.count("loadGlossary("), 2)
        self.assertEqual(source.count("loadGlossaryChrome("), 2)
        self.assertIn("const glossaryResultPromise = loadGlossary().then(", source)
        self.assertIn("const chromeResultPromise = currentGlossaryStrings().then(", source)
        self.assertIn('dialog = document.createElement("dialog");', source)
        self.assertIn("void openDefinition(trigger);", source)
        self.assertIn("void openDefinition(control);", source)
        self.assertLess(source.index("async function openDefinition"), source.index("loadGlossary().then("))
        self.assertNotIn("DOMContentLoaded", source)
        self.assertNotIn("requestIdleCallback", source)

    def test_failed_fetches_can_retry_on_later_activation(self) -> None:
        source = JS.read_text(encoding="utf-8")
        self.assertIn("glossaryPromise = undefined;", source)
        self.assertIn("chromePromise = undefined;", source)
        self.assertGreaterEqual(source.count("throw error;"), 2)

    def test_pending_activation_exposes_and_clears_accessible_busy_state(self) -> None:
        source = JS.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8")
        self.assertIn("function setPendingTrigger(trigger)", source)
        self.assertIn('trigger.setAttribute("aria-busy", "true");', source)
        self.assertIn("function clearPendingTrigger(trigger)", source)
        self.assertIn('current.removeAttribute("aria-busy");', source)
        self.assertGreaterEqual(source.count("clearPendingTrigger("), 7)
        self.assertIn('.glossary-term[aria-busy="true"]', css)
        self.assertIn("cursor: progress", css)

    def test_runtime_preserves_static_link_fallback_and_modified_clicks(self) -> None:
        source = JS.read_text(encoding="utf-8")
        self.assertIn("data-glossary-static-fallback", source)
        self.assertIn(':not([data-glossary-static-fallback="true"])', source)
        self.assertIn('trigger.dataset.glossaryHref = link.getAttribute("href")', source)
        self.assertIn('panel.querySelector(".glossary-inline-dialog__actions a").href = fallbackHref(trigger);', source)
        self.assertIn("function restoreFallbackLink(trigger)", source)
        self.assertIn('link.dataset.glossaryStaticFallback = "true";', source)
        self.assertIn('link.setAttribute("href", fallbackHref(trigger));', source)
        self.assertIn('control.dataset.glossaryStaticFallback === "true"', source)
        self.assertNotIn("window.location.assign", source)
        for modifier in ("event.metaKey", "event.ctrlKey", "event.shiftKey", "event.altKey"):
            self.assertIn(modifier, source)
        self.assertIn('event.key !== "Escape"', source)
        self.assertIn('dialog.setAttribute("aria-labelledby"', source)
        self.assertIn('dialog.setAttribute("aria-describedby"', source)
        self.assertIn("restore.focus({ preventScroll: true })", source)

    def test_chrome_locale_failure_restores_progressive_link_fallback(self) -> None:
        source = JS.read_text(encoding="utf-8")
        self.assertIn('console.warn("Glossary chrome loading failed", chromeResult.error);', source)
        self.assertIn("restoreFallbackLink(trigger);", source)
        self.assertLess(
            source.index('console.warn("Glossary chrome loading failed"'),
            source.index("restoreFallbackLink(trigger);"),
        )

    def test_runtime_guards_navigation_races_and_active_trigger_containment(self) -> None:
        source = JS.read_text(encoding="utf-8")
        self.assertIn("let pendingTrigger;", source)
        self.assertIn("setPendingTrigger(trigger);", source)
        self.assertGreaterEqual(source.count("pendingTrigger !== trigger"), 1)
        self.assertGreaterEqual(source.count("!trigger.isConnected"), 1)
        self.assertIn("!pendingTrigger.contains(target)", source)
        self.assertIn("!activeTrigger.contains(target)", source)

    def test_detached_active_trigger_closes_dialog_after_instant_navigation(self) -> None:
        source = JS.read_text(encoding="utf-8")
        self.assertIn("function closeDetachedDialog()", source)
        self.assertIn("activeTrigger && !activeTrigger.isConnected", source)
        self.assertIn("navigationObserver = new MutationObserver((records) => {", source)
        self.assertIn("closeDetachedDialog();", source)
        self.assertIn("enhanceGlossaryLinks(node);", source)
        self.assertIn("navigationObserver.observe(document.body", source)
        self.assertIn("childList: true", source)
        self.assertIn("subtree: true", source)

    def test_detached_dialog_is_reattached_on_subsequent_activation(self) -> None:
        source = JS.read_text(encoding="utf-8")
        self.assertIn("function observeNavigationBody()", source)
        self.assertIn("if (!dialog.isConnected)", source)
        self.assertGreaterEqual(source.count("document.body.appendChild(dialog);"), 2)
        self.assertIn("navigationObserver.disconnect();", source)
        self.assertGreaterEqual(source.count("observeNavigationBody();"), 3)
        self.assertIn("applyDialogChrome(dialog, strings);", source)

    def test_escape_cancels_pending_open_and_pointer_dismissal_does_not_restore_focus(self) -> None:
        source = JS.read_text(encoding="utf-8")
        self.assertIn("let pointerDismissal = false;", source)
        self.assertIn("pointerDismissal = true;", source)
        self.assertIn("!pointerDismissal", source)
        self.assertIn("clearPendingTrigger();", source)

    def test_open_dialog_repositions_and_clamps_within_viewport(self) -> None:
        source = JS.read_text(encoding="utf-8")
        self.assertIn("function repositionOpenDialog()", source)
        self.assertIn("positionDialog(activeTrigger, dialog);", source)
        self.assertIn('window.addEventListener("resize", repositionOpenDialog);', source)
        self.assertIn('document.addEventListener("scroll", repositionOpenDialog, {', source)
        self.assertIn("capture: true", source)
        self.assertIn("passive: true", source)
        self.assertIn("const preferredTop = Math.max(", source)
        self.assertIn("viewportPadding,", source)

    def test_explanation_metadata_and_provider_labels_follow_glossary_contract(self) -> None:
        source = JS.read_text(encoding="utf-8")
        self.assertIn('term.origin === "repository" && typeof term.definition === "string"', source)
        self.assertIn('typeof term.summary === "string"', source)
        self.assertIn("return term.definition;", source)
        self.assertIn("return term.summary;", source)
        self.assertIn("return strings.definition_unavailable;", source)
        self.assertIn('site: "Site"', source)
        self.assertIn('composition: "Composition"', source)
        self.assertIn('policy: "Policy"', source)
        self.assertNotIn('skill: "Skill"', source)
        self.assertNotIn('webapp: "Webapp"', source)
        self.assertIn("`${strings.external_term_prefix} ${owner}`", source)
        self.assertIn("`${strings.repository_term_prefix} ${owner}`", source)

    def test_enhanced_trigger_uses_native_button_dialog_semantics(self) -> None:
        source = JS.read_text(encoding="utf-8")
        self.assertIn('const trigger = document.createElement("button");', source)
        self.assertIn('trigger.type = "button";', source)
        self.assertIn('trigger.setAttribute("aria-haspopup", "dialog");', source)
        self.assertIn('trigger.setAttribute("aria-controls", DIALOG_ID);', source)
        self.assertIn('trigger.setAttribute("aria-expanded", "false");', source)
        self.assertIn('trigger.setAttribute("aria-expanded", "true");', source)
        self.assertIn('restore.setAttribute("aria-expanded", "false");', source)
        self.assertIn("link.replaceWith(trigger);", source)

    def test_runtime_failure_stays_in_place_and_exposes_localized_explicit_navigation(self) -> None:
        source = JS.read_text(encoding="utf-8")
        self.assertIn("fillErrorDialog(panel, trigger, strings.definition_load_failed, strings);", source)
        self.assertIn("fillErrorDialog(panel, trigger, strings.definition_not_found, strings);", source)
        self.assertIn("strings.data_unavailable", source)
        self.assertIn("strings.open_in_glossary", source)
        self.assertNotIn("Definition could not be loaded.", source)
        self.assertNotIn("Definition could not be found.", source)
        self.assertNotIn("Open in Glossary", source)
        self.assertNotIn("window.location", source)

    def test_dialog_chrome_uses_text_apis_for_locale_strings(self) -> None:
        source = JS.read_text(encoding="utf-8")
        self.assertIn("function applyDialogChrome(panel, strings)", source)
        self.assertIn(".textContent = strings.eyebrow", source)
        self.assertIn("strings.close_definition", source)
        self.assertIn(".textContent = strings.open_in_glossary", source)
        self.assertNotIn("${strings.eyebrow}", source)
        self.assertNotIn("${strings.open_in_glossary}", source)

    def test_annotation_style_does_not_change_static_link_text_metrics(self) -> None:
        source = CSS.read_text(encoding="utf-8")
        annotation_rule = source.split(".glossary-term {", 1)[1].split("}", 1)[0]
        busy_rule = source.split('.glossary-term[aria-busy="true"] {', 1)[1].split("}", 1)[0]
        self.assertIn("text-decoration", annotation_rule)
        self.assertIn("cursor: help", annotation_rule)
        for rule in (annotation_rule, busy_rule):
            self.assertNotIn("font-size", rule)
            self.assertNotIn("font-weight", rule)
            self.assertNotIn("line-height", rule)
            self.assertNotIn("padding", rule)
            self.assertNotIn("margin", rule)

    def test_enhanced_button_resets_user_agent_metrics(self) -> None:
        source = CSS.read_text(encoding="utf-8")
        button_rule = source.split("button.glossary-term {", 1)[1].split("}", 1)[0]
        for declaration in (
            "appearance: none",
            "display: inline",
            "margin: 0",
            "padding: 0",
            "border: 0",
            "background: none",
            "font: inherit",
            "line-height: inherit",
            "vertical-align: baseline",
        ):
            self.assertIn(declaration, button_rule)

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
        project = tomllib.loads(template.replace("__GENERATED_NAV__", "[]"))["project"]
        self.assertEqual(
            project["extra_css"],
            [
                "stylesheets/extra.css",
                "stylesheets/landing-cover.css",
                "stylesheets/landing-shell.css",
                "stylesheets/mobile-density.css",
                "stylesheets/translation-reader.css",
                "stylesheets/glossary-inline.css",
                "stylesheets/freshness-status.css",
            ],
        )
        self.assertEqual(
            project["extra_javascript"],
            [
                "javascripts/repository-tree-viewer.js",
                "javascripts/pwa.js",
                "javascripts/reader-navigation.js",
                "javascripts/glossary-inline.js",
            ],
        )
        self.assertIn('"navigation.instant"', template)
        self.assertNotIn("/glossary/index.json", template)
        self.assertNotIn("/site-chrome-locales.json", template)


if __name__ == "__main__":
    unittest.main()
