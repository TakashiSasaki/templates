from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "assets/javascripts/reader-navigation.js"
STYLES = ROOT / "assets/stylesheets/extra.css"
TEMPLATE = ROOT / "zensical.template.toml"
WORKER = ROOT / "assets/service-worker.js"


class SearchHistoryRuntimeContractTests(unittest.TestCase):
    def runtime(self) -> str:
        return RUNTIME.read_text(encoding="utf-8")

    def history_runtime(self) -> str:
        source = self.runtime()
        return source.split("/* Site-local search history.", 1)[1]

    def test_history_uses_origin_scoped_bounded_local_storage(self) -> None:
        source = self.history_runtime()
        self.assertIn(
            'const SEARCH_HISTORY_STORAGE_KEY = "templates.search-history.v1";',
            source,
        )
        self.assertIn("const MAX_SEARCH_HISTORY = 10;", source)
        self.assertIn("window.localStorage.getItem(SEARCH_HISTORY_STORAGE_KEY)", source)
        self.assertIn("window.localStorage.setItem(", source)
        self.assertIn("window.localStorage.removeItem(SEARCH_HISTORY_STORAGE_KEY)", source)
        self.assertIn("JSON.parse(raw)", source)
        self.assertIn("JSON.stringify(history.slice(0, MAX_SEARCH_HISTORY))", source)
        self.assertNotIn("sessionStorage", source)
        self.assertNotIn("indexedDB", source)

    def test_query_normalization_deduplicates_and_keeps_most_recent_first(self) -> None:
        source = self.history_runtime()
        self.assertIn('value.normalize("NFC").trim().replace(/\\s+/gu, " ")', source)
        self.assertIn("return normalizeQuery(value).toLowerCase();", source)
        self.assertIn("const next = [", source)
        self.assertIn("query,", source)
        self.assertIn("queryKey(item) !== key", source)
        self.assertIn("].slice(0, MAX_SEARCH_HISTORY);", source)
        self.assertIn("const seen = new Set();", source)

    def test_partial_typing_is_not_written_to_history(self) -> None:
        source = self.history_runtime()
        input_listener = source.split(
            'input.addEventListener("input", () => renderSearchHistory(root));',
            1,
        )[0]
        self.assertNotIn('input.addEventListener("input", () => rememberQuery', source)
        self.assertIn('input.addEventListener("input", () => renderSearchHistory(root));', source)
        self.assertIn("rememberQuery(input.value);", source)
        self.assertIn("const resultLink = target.closest(SEARCH_RESULT_LINK_SELECTOR);", source)
        self.assertNotIn("rememberQuery(input.value);", input_listener)

    def test_result_activation_and_history_replay_use_zensical_search_contract(self) -> None:
        source = self.history_runtime()
        self.assertIn(
            'const SEARCH_INPUT_SELECTOR = \'[data-md-component="search-query"]\';',
            source,
        )
        self.assertIn(
            'const SEARCH_RESULT_LINK_SELECTOR = "a.md-search-result__link[href]";',
            source,
        )
        self.assertIn('!resultLink.closest("[data-site-search-history]")', source)
        self.assertIn("input.value = query;", source)
        self.assertIn('input.dispatchEvent(new Event("input", { bubbles: true }));', source)
        self.assertIn("input.focus({ preventScroll: true });", source)
        self.assertIn('input.form?.addEventListener("reset", () => {', source)
        self.assertIn("queueMicrotask(() => renderSearchHistory(root));", source)

    def test_history_controls_do_not_join_zensical_result_navigation(self) -> None:
        source = self.history_runtime()
        self.assertIn('button.className = "site-search-history__link";', source)
        self.assertIn('button.type = "button";', source)
        self.assertIn('clear.type = "button";', source)
        self.assertNotIn('link.className = "md-search-result__link";', source)
        self.assertNotIn('item.className = "md-search-result__item";', source)
        self.assertNotIn('section.className = "md-search-result site-search-history";', source)

    def test_history_ui_is_dom_safe_clearable_and_localized_for_site_languages(self) -> None:
        source = self.history_runtime()
        styles = STYLES.read_text(encoding="utf-8")
        self.assertIn('heading: "Recent searches"', source)
        self.assertIn('clear: "Clear history"', source)
        self.assertIn('heading: "最近の検索"', source)
        self.assertIn('clear: "履歴を消去"', source)
        self.assertIn('section.setAttribute("aria-label", strings.heading);', source)
        self.assertIn("heading.textContent = strings.heading;", source)
        self.assertIn("clear.textContent = strings.clear;", source)
        self.assertIn("title.textContent = query;", source)
        self.assertIn("list.replaceChildren();", source)
        self.assertNotIn("innerHTML", source)
        self.assertIn("clearHistory();", source)
        self.assertIn(".site-search-history__link:focus-visible", styles)
        self.assertIn("overflow-wrap: anywhere", styles)

    def test_search_history_survives_instant_navigation_and_cross_tab_updates(self) -> None:
        source = self.history_runtime()
        self.assertIn('root.dataset.siteSearchHistoryEnhanced = "true";', source)
        self.assertIn('window.addEventListener("pageshow", enhanceSearchHistory);', source)
        self.assertIn('window.addEventListener("popstate", enhanceSearchHistory);', source)
        self.assertIn('window.addEventListener("storage", (event) => {', source)
        self.assertIn("navigationDocument.subscribe(enhanceSearchHistory);", source)
        self.assertIn("document.querySelectorAll(SEARCH_ROOT_SELECTOR)", source)

    def test_search_terms_remain_local_and_are_not_transmitted(self) -> None:
        source = self.history_runtime()
        self.assertNotIn("fetch(", source)
        self.assertNotIn("sendBeacon", source)
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotIn("WebSocket", source)

    def test_runtime_and_styles_are_already_in_zensical_and_pwa_shell(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        worker = WORKER.read_text(encoding="utf-8")
        self.assertIn('"javascripts/reader-navigation.js"', template)
        self.assertIn('"stylesheets/extra.css"', template)
        match = re.search(r"const STATIC_ASSETS = (\[[^;]+\]);", worker)
        self.assertIsNotNone(match)
        static_assets = set(json.loads(match.group(1)))
        self.assertIn("/javascripts/reader-navigation.js", static_assets)
        self.assertIn("/stylesheets/extra.css", static_assets)


if __name__ == "__main__":
    unittest.main()
