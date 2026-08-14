from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-pages.yml"


class GuidedLocaleWorkflowTests(unittest.TestCase):
    def test_locale_pipeline_runs_in_authority_preserving_order(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        graph = text.index("- name: Generate index navigation graph")
        overlay = text.index("- name: Generate index navigation locale overlays")
        canonical_viewer = text.index("- name: Generate index-guided navigation viewer")
        locale_viewer = text.index("- name: Generate localized index-guided navigation viewer")
        canonical_metadata = text.index("- name: Normalize guided canonical links and PWA metadata")
        reader_metadata = text.index("- name: Finalize per-page and translation reader metadata")
        locale_metadata = text.index("- name: Finalize localized guided metadata")
        verify = text.index("- name: Verify generated public URL boundary")
        self.assertLess(graph, overlay)
        self.assertLess(overlay, canonical_viewer)
        self.assertLess(canonical_viewer, locale_viewer)
        self.assertLess(locale_viewer, canonical_metadata)
        self.assertLess(canonical_metadata, reader_metadata)
        self.assertLess(reader_metadata, locale_metadata)
        self.assertLess(locale_metadata, verify)

    def test_japanese_guided_routes_are_verified_without_localized_graph(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("test -f build/site/ja/guided/index.html", text)
        self.assertIn("test ! -e build/site/ja/guided/graph.json", text)
        self.assertIn("build/index-navigation-locales.json", text)
        self.assertIn("build/guided-locale-publication.json", text)


if __name__ == "__main__":
    unittest.main()
