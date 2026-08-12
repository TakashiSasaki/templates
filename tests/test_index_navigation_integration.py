from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
LANDING = ROOT / "docs/landing.md"
OVERVIEW = ROOT / "docs/overview.md"
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
        viewer = workflow.index("- name: Generate index-guided navigation viewer")
        guided_metadata = workflow.index(
            "- name: Normalize guided canonical links and PWA metadata"
        )
        entry_points = workflow.index("- name: Verify the Pages entry point")
        link_validation = workflow.index("- name: Validate generated site links")

        self.assertLess(static_build, browser)
        self.assertLess(browser, graph)
        self.assertLess(graph, viewer)
        self.assertLess(viewer, guided_metadata)
        self.assertLess(guided_metadata, entry_points)
        self.assertLess(entry_points, link_validation)

        for provider in ("skill", "policy", "webapp"):
            self.assertEqual(
                workflow.count(f"--provider {provider}={provider}-source"),
                2,
            )
            self.assertIn(
                f'build/site/guided/${{provider}}/index.html',
                workflow,
            )
        self.assertIn("--output build/index-navigation.json", workflow)
        self.assertIn("--graph build/index-navigation.json", workflow)
        self.assertIn("--site-root build/site/guided", workflow)
        self.assertIn("build/site/guided/graph.json", workflow)
        self.assertIn("missing guided index page", workflow)
        self.assertGreaterEqual(
            workflow.count('<link rel="manifest" href="/app.webmanifest">'),
            2,
        )
        self.assertGreaterEqual(
            workflow.count('<meta name="theme-color" content="#3f51b5">'),
            2,
        )

    def test_reader_surfaces_expose_guided_discovery_as_a_distinct_path(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        overview = OVERVIEW.read_text(encoding="utf-8")
        self.assertIn('href="/guided/"', landing)
        self.assertIn("Browse by index.md", landing)
        self.assertIn('href="files/"', landing)
        self.assertIn('href="overview/"', landing)
        self.assertIn('href="../guided/"', overview)
        self.assertIn("Browse by index.md", overview)

    def test_publication_policy_defines_provider_owned_guided_boundary(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        normalized = " ".join(policy.split())

        self.assertIn("### Index-guided navigation", policy)
        self.assertIn("provider-owned `index.md`", policy)
        self.assertIn("/guided/graph.json", policy)
        self.assertIn("cycles, multiple navigation parents, and maximum index depth", normalized)
        self.assertIn("human viewer consumes that graph rather than reparsing provider Markdown", normalized)
        self.assertIn("graph revision for a provider must equal the checked-out provider revision", normalized)
        self.assertIn("not a second catalog", normalized)
        self.assertIn("must not silently derive or replace its primary navigation", normalized)

    def test_maintenance_and_readme_include_guided_build_contract(self) -> None:
        maintenance = MAINTENANCE.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        for text in (maintenance, readme):
            self.assertIn("scripts/generate_index_navigation.py", text)
            self.assertIn("scripts/generate_index_navigation_viewer.py", text)
            self.assertIn("--site-root build/site/guided", text)
        self.assertIn("## Index-guided navigation generation", maintenance)
        self.assertIn("/guided/", readme)

    def test_provider_lock_remains_an_independent_full_sha_dependency_lock(self) -> None:
        lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
        self.assertEqual(set(lock["publications"]), {"skill", "policy", "webapp"})
        for provider, entry in lock["publications"].items():
            with self.subTest(provider=provider):
                revision = entry["revision"]
                self.assertEqual(len(revision), 40)
                self.assertEqual(revision, revision.lower())
                self.assertTrue(all(character in "0123456789abcdef" for character in revision))


if __name__ == "__main__":
    unittest.main()