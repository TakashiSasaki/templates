from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
LANDING = ROOT / "docs/landing.md"
POLICY = ROOT / "PUBLISHING.md"
MAINTENANCE = ROOT / "MAINTENANCE.md"
README = ROOT / "README.md"
SOURCE_LOCK = ROOT / "publication-sources.json"


class IndexNavigationIntegrationTests(unittest.TestCase):
    def test_pages_build_orders_browser_graph_viewer_metadata_and_link_validation(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        static_build = workflow.index("- name: Build the static site")
        browser = workflow.index("- name: Generate static repository browser")
        graph = workflow.index("- name: Generate index navigation graph")
        overlay = workflow.index("- name: Generate index navigation locale overlays")
        viewer = workflow.index("- name: Generate index-guided navigation viewer")
        locale_viewer = workflow.index(
            "- name: Generate localized index-guided navigation viewer"
        )
        guided_metadata = workflow.index(
            "- name: Normalize guided canonical links and PWA metadata"
        )
        reader_metadata = workflow.index(
            "- name: Finalize per-page and translation reader metadata"
        )
        locale_metadata = workflow.index("- name: Finalize localized guided metadata")
        entry_points = workflow.index("- name: Verify the Pages entry point")
        link_validation = workflow.index("- name: Validate generated site links")

        self.assertLess(static_build, browser)
        self.assertLess(browser, graph)
        self.assertLess(graph, overlay)
        self.assertLess(overlay, viewer)
        self.assertLess(viewer, locale_viewer)
        self.assertLess(locale_viewer, guided_metadata)
        self.assertLess(guided_metadata, reader_metadata)
        self.assertLess(reader_metadata, locale_metadata)
        self.assertLess(locale_metadata, entry_points)
        self.assertLess(entry_points, link_validation)

        for provider in ("composition", "policy"):
            self.assertEqual(
                workflow.count(f"--provider {provider}={provider}-source"),
                4,
            )
            self.assertIn(
                f'build/site/guided/${{provider}}/index.html',
                workflow,
            )
        self.assertNotIn("--provider skill=", workflow)
        self.assertNotIn("--provider webapp=", workflow)
        self.assertEqual(
            workflow.count("scripts/run_composition_navigation.py"),
            4,
        )
        for mode in ("graph", "locales", "viewer", "locale-viewer"):
            self.assertIn(f"run_composition_navigation.py {mode}", workflow)
        self.assertIn("--output build/index-navigation.json", workflow)
        self.assertIn("--graph build/index-navigation.json", workflow)
        self.assertIn("--output build/index-navigation-locales.json", workflow)
        self.assertIn("--locale-overlays build/index-navigation-locales.json", workflow)
        self.assertIn("--pair-map build/guided-locale-publication.json", workflow)
        self.assertIn("--site-root build/site/guided", workflow)
        self.assertIn("build/site/guided/graph.json", workflow)
        self.assertIn("guided graph provider order mismatch", workflow)
        self.assertIn("test ! -e build/site/ja/guided/graph.json", workflow)
        self.assertIn("missing guided index page", workflow)

    def test_reader_surfaces_expose_guided_discovery_as_a_distinct_path(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        self.assertIn('href="/guided/"', landing)
        self.assertIn("Browse by index.md", landing)
        self.assertIn('href="files/"', landing)
        self.assertNotIn('href="overview/"', landing)

    def test_publication_policy_defines_provider_owned_guided_boundary(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")

        self.assertIn("## Index-guided navigation", policy)
        self.assertIn("Provider-owned `docs/index.md`", policy)
        self.assertIn("composition", policy)
        self.assertIn("policy", policy)
        self.assertIn("exact full-SHA provider revisions", policy)

    def test_maintenance_and_readme_include_guided_build_contract(self) -> None:
        maintenance = MAINTENANCE.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        for text in (maintenance, readme):
            self.assertIn("scripts/run_composition_navigation.py", text)
            self.assertIn("--site-root build/site/guided", text)
        self.assertIn("## Index-guided navigation generation", maintenance)
        self.assertIn("/guided/", readme)

    def test_provider_lock_remains_a_full_sha_dependency_lock(self) -> None:
        lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
        self.assertEqual(set(lock["publications"]), {"composition", "policy"})
        for provider, entry in lock["publications"].items():
            with self.subTest(provider=provider):
                revision = entry["revision"]
                self.assertEqual(len(revision), 40)
                self.assertEqual(revision, revision.lower())
                self.assertTrue(all(character in "0123456789abcdef" for character in revision))


if __name__ == "__main__":
    unittest.main()
