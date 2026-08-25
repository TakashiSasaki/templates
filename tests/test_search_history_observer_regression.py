from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "assets/javascripts/reader-navigation.js"


class SearchHistoryObserverRegressionTests(unittest.TestCase):
    def search_runtime(self) -> str:
        source = RUNTIME.read_text(encoding="utf-8")
        marker = "/* Site-local search history integrated through Zensical's open Shadow DOM contract. */"
        self.assertIn(marker, source)
        return source.split(marker, 1)[1]

    def test_site_owned_history_mutations_do_not_reenter_render_loop(self) -> None:
        source = self.search_runtime()
        self.assertIn("list.replaceChildren();", source)
        self.assertIn("function mutationTargetsSiteOwnedNode(state, record)", source)
        self.assertIn("target === state.section", source)
        self.assertIn("state.section.contains(target)", source)
        self.assertIn("const observer = new MutationObserver((records) => {", source)
        self.assertIn(
            "records.some((record) => !mutationTargetsSiteOwnedNode(state, record))",
            source,
        )
        self.assertNotIn("const observer = new MutationObserver(() => {", source)

    def test_unchanged_history_keeps_control_nodes_stable_during_focus_changes(self) -> None:
        source = self.search_runtime()
        self.assertIn("const existingQueries = Array.from(", source)
        self.assertIn("existingQueries.length === history.length", source)
        self.assertIn("existingQueries.every((query, index) => query === history[index])", source)
        guard = source.index("existingQueries.length === history.length")
        replace = source.index("list.replaceChildren();")
        self.assertLess(guard, replace)


if __name__ == "__main__":
    unittest.main()
