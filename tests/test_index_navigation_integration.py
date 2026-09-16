from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/site-producer.yml"
LANDING = ROOT / "docs/landing.md"
POLICY = ROOT / "PUBLISHING.md"
MAINTENANCE = ROOT / "MAINTENANCE.md"
README = ROOT / "README.md"
SOURCE_LOCK = ROOT / "publication-sources.json"


class IndexNavigationIntegrationTests(unittest.TestCase):
    def test_pages_build_orders_browser_graph_viewer_metadata_and_link_validation(self) -> None:
        workflow = WORKFLOW.read_text()
        self.assertLess(workflow.index('- name: Consume exact qualified Publication Bundle'),workflow.index('- name: Render Site from validated Publication Bundle'))
        text = (Path(__file__).resolve().parents[1] / 'site_renderer/render.py').read_text()
        ordered = ["'zensical'))", 'browser.prepare_browser_root(', 'guided.generate_from_bundle(', 'guided_locales.generate_from_bundle(', "'finalize_translation_reader.py'", "'finalize_guided_locales.py'", "'validate_site_links.py'"]
        self.assertEqual([text.index(token) for token in ordered], sorted(text.index(token) for token in ordered))
        for assertion in ('scripts/check_bundle_reader.py', 'test -f build/site/guided/graph.json'):
            self.assertIn(assertion,workflow)
        self.assertNotIn('--provider composition=',text)
        self.assertNotIn('--provider policy=',text)

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
