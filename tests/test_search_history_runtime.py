from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "assets/javascripts/reader-navigation.js"
TEMPLATE = ROOT / "zensical.template.toml"
WORKER = ROOT / "assets/service-worker.js"
BROWSER_CHECK = ROOT / "scripts/check_search_history.py"
REVIEW_BROWSER_CHECK = ROOT / "scripts/check_search_history_review_regressions.py"
BUILD_WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
SEARCH_WORKFLOW = ROOT / ".github/workflows/search-history-regression.yml"


class SearchHistoryRuntimeContractTests(unittest.TestCase):
    def search_runtime(self) -> str:
        source = RUNTIME.read_text(encoding="utf-8")
        marker = "/* Site-local search history integrated through Zensical's open Shadow DOM contract. */"
        self.assertIn(marker, source)
        return source.split(marker, 1)[1]

    def test_zensical_boundary_uses_open_shadow_root_semantics(self) -> None:
        source = self.search_runtime()
        self.assertIn("for (const host of document.body.children)", source)
        self.assertIn("if (host.shadowRoot)", source)
        self.assertIn("root.querySelector(SEARCH_INPUT_SELECTOR)", source)
        self.assertIn("const SEARCH_INPUT_SELECTOR = 'input[role=\"combobox\"]';", source)
        self.assertIn('root.querySelectorAll("ol a[href]")', source)
        self.assertNotIn(".md-search__scrollwrap", source)
        self.assertNotIn("md-search-result__link", source)
        self.assertNotIn('data-md-component="search-query"', source)

    def test_search_open_state_is_derived_from_visible_shadow_ui(self) -> None:
        source = self.search_runtime()
        self.assertIn("function searchInputIsInteractive(input)", source)
        self.assertIn('inputStyle.pointerEvents === "none"', source)
        self.assertIn("Number.parseFloat(style.opacity) === 0", source)
        self.assertIn("const rect = input.getBoundingClientRect();", source)
        self.assertIn("return rect.width > 0 && rect.height > 0;", source)
        self.assertNotIn("SEARCH_TOGGLE_SELECTOR", source)
        self.assertNotIn("toggle?.checked", source)

    def test_history_uses_origin_scoped_bounded_fail_open_local_storage(self) -> None:
        source = self.search_runtime()
        self.assertIn('const SEARCH_HISTORY_STORAGE_KEY = "templates.search-history.v1";', source)
        self.assertIn("const SEARCH_HISTORY_LIMIT = 10;", source)
        self.assertIn("window.localStorage.getItem(SEARCH_HISTORY_STORAGE_KEY)", source)
        self.assertIn("window.localStorage.setItem(", source)
        self.assertIn("window.localStorage.removeItem(SEARCH_HISTORY_STORAGE_KEY)", source)
        self.assertGreaterEqual(source.count("catch (_error)"), 3)
        history_storage_block = source.split("function loadHistory()", 1)[1].split("function currentStrings()", 1)[0]
        self.assertNotIn("sessionStorage", history_storage_block)

    def test_queries_are_normalized_deduplicated_and_mru_ordered(self) -> None:
        source = self.search_runtime()
        self.assertIn('value.normalize("NFC").trim().replace(/\\s+/gu, " ")', source)
        self.assertIn("return normalizeQuery(value).toLowerCase();", source)
        self.assertIn("const seen = new Set();", source)
        self.assertIn("queryKey(item) !== key", source)
        self.assertIn("].slice(0, SEARCH_HISTORY_LIMIT);", source)

    def test_typing_does_not_commit_but_real_result_click_does(self) -> None:
        source = self.search_runtime()
        self.assertIn('input.addEventListener("input", () => {', source)
        self.assertIn('const anchor = target.closest("a[href]");', source)
        self.assertIn('anchor.closest("ol")', source)
        self.assertIn("rememberQuery(current.input.value);", source)
        input_block = source.split('input.addEventListener("input", () => {', 1)[1].split("});", 1)[0]
        self.assertNotIn("rememberQuery", input_block)

    def test_enter_stages_then_requires_confirmed_navigation_before_commit(self) -> None:
        source = self.search_runtime()
        self.assertIn("const PENDING_ENTER_MAX_AGE_MS = 1000;", source)
        self.assertIn('const PENDING_ENTER_SESSION_KEY = "templates.search-history.pending-enter.v1";', source)
        self.assertIn("const PENDING_ENTER_SESSION_MAX_AGE_MS = 15000;", source)
        self.assertIn("function stagePendingEnter(state)", source)
        self.assertIn("const maxAgeMs = hasNavigationApi", source)
        self.assertIn("? PENDING_ENTER_MAX_AGE_MS", source)
        self.assertIn(": PENDING_ENTER_SESSION_MAX_AGE_MS;", source)
        self.assertIn("expiresAt: Date.now() + maxAgeMs", source)
        self.assertIn("}, maxAgeMs);", source)
        self.assertIn("function confirmPendingEnterNavigation(destination)", source)
        self.assertIn("function storePendingEnterForNextDocument()", source)
        self.assertIn("function confirmStoredPendingEnterNavigation()", source)
        self.assertIn('window.navigation.addEventListener("navigate", (event) => {', source)
        self.assertIn('confirmPendingEnterNavigation(event.destination?.url || "")', source)
        self.assertIn('window.addEventListener("pagehide", storePendingEnterForNextDocument);', source)
        self.assertIn('window.addEventListener("hashchange", () => {', source)
        self.assertIn('window.sessionStorage.setItem(', source)
        self.assertIn('window.sessionStorage.removeItem(PENDING_ENTER_SESSION_KEY)', source)
        self.assertNotIn('confirmPendingEnterNavigation(window.location.href);\n    });\n  }', source)
        self.assertIn('"keydown",', source)
        self.assertIn("stagePendingEnter(current);", source)
        keydown_block = source.split('"keydown",', 1)[1].split("true,", 1)[0]
        self.assertNotIn("rememberQuery", keydown_block)
        self.assertIn("cancelPendingEnter(current);", source)

    def test_replay_uses_react_compatible_bubbling_input_event(self) -> None:
        source = self.search_runtime()
        self.assertIn('Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")', source)
        self.assertIn("descriptor.set.call(input, value);", source)
        self.assertIn('new InputEvent("input", { bubbles: true, inputType: "insertText", data: query })', source)
        self.assertIn("state.input.dispatchEvent(inputEvent);", source)
        self.assertIn('button.addEventListener("click", (event) => replayQuery(event, state, button));', source)

    def test_site_owned_controls_are_isolated_before_shadow_root_delegation(self) -> None:
        source = self.search_runtime()
        self.assertIn('clearControl.addEventListener("click", (event) => {', source)
        clear_block = source.split('clearControl.addEventListener("click", (event) => {', 1)[1].split("});", 1)[0]
        self.assertIn("event.stopPropagation();", clear_block)
        self.assertIn('button.addEventListener("click", (event) => replayQuery(event, state, button));', source)

    def test_disconnected_input_hides_site_overlay(self) -> None:
        source = self.search_runtime()
        self.assertIn("if (!state.input.isConnected) {", source)
        disconnected = source.split("if (!state.input.isConnected) {", 1)[1].split("}", 1)[0]
        self.assertIn("state.section.hidden = true;", disconnected)

    def test_instant_navigation_shadow_host_replacement_and_cross_tab_updates_are_rebound(self) -> None:
        source = self.search_runtime()
        self.assertIn("const observedRoots = new WeakMap();", source)
        self.assertIn("new MutationObserver((records) => {", source)
        self.assertIn('attributeFilter: ["class"]', source)
        self.assertIn("!state.style.isConnected", source)
        self.assertIn("!state.section.isConnected", source)
        self.assertIn('window.addEventListener("pageshow", initializeSearchHistory);', source)
        self.assertIn('window.addEventListener("storage", (event) => {', source)

    def test_query_terms_are_not_sent_by_site_history_runtime(self) -> None:
        source = self.search_runtime()
        self.assertNotIn("sendBeacon", source)
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotIn("WebSocket", source)

    def test_precached_runtime_and_built_artifact_browser_checks_are_part_of_ci(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        worker = WORKER.read_text(encoding="utf-8")
        checker = BROWSER_CHECK.read_text(encoding="utf-8")
        review_checker = REVIEW_BROWSER_CHECK.read_text(encoding="utf-8")
        build_workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
        search_workflow = SEARCH_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('"javascripts/reader-navigation.js"', template)
        match = re.search(r"const STATIC_ASSETS = (\[[^;]+\]);", worker)
        self.assertIsNotNone(match)
        self.assertIn("/javascripts/reader-navigation.js", set(json.loads(match.group(1))))
        self.assertIn("Zensical search integration contract changed", checker)
        self.assertIn("search_input.click(trial=True", checker)
        self.assertIn("result = page.locator('ol a[href]').first", review_checker)
        self.assertIn("root?.addEventListener(\n            'click'", review_checker)
        self.assertIn("event instanceof InputEvent", review_checker)
        self.assertIn("JSON.stringify(now) !== JSON.stringify(before)", review_checker)
        self.assertIn("page.expect_navigation", review_checker)
        self.assertIn("cancelled Enter recorded history", review_checker)
        self.assertIn("normal Enter wrote history", review_checker)
        self.assertIn("install_no_navigation_api", review_checker)
        self.assertIn("fallback mismatched destination recorded history", review_checker)
        self.assertIn("delayed fallback same-document signal did not store policy", review_checker)
        self.assertIn("new PopStateEvent('popstate')", review_checker)
        self.assertIn("fallback_delayed_same_document_wait_ms", review_checker)
        self.assertIn("fallback_delayed_same_document_no_pagehide_handoff", review_checker)
        self.assertIn("fallback Enter did not store policy after confirmed navigation", review_checker)
        self.assertIn("fallback Enter left pending state after confirmation", review_checker)

        self.assertIn("workflow_dispatch:", search_workflow)
        self.assertIn("run_id:", search_workflow)
        self.assertIn("site_ref:", search_workflow)
        self.assertNotIn("Wait for documentation artifact build", search_workflow)
        self.assertNotIn("actions/github-script", search_workflow)
        self.assertNotIn("pull_request:", search_workflow)
        self.assertIn("python scripts/check_search_history.py", search_workflow)
        self.assertIn("python scripts/check_search_history_review_regressions.py", search_workflow)

        check_block = build_workflow.split("\n  check:\n", 1)[1]
        self.assertIn("needs: build", check_block)
        self.assertIn("actions/download-artifact@v5", check_block)
        self.assertIn("python scripts/check_search_history.py", check_block)
        self.assertIn("python scripts/check_search_history_review_regressions.py", check_block)
        self.assertIn("name: search-history-${{ github.event.pull_request.number }}", check_block)


if __name__ == "__main__":
    unittest.main()