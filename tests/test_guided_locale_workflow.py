from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "site-producer.yml"


class GuidedLocaleWorkflowTests(unittest.TestCase):
    def test_locale_pipeline_runs_in_authority_preserving_order(self) -> None:
        text = (Path(__file__).resolve().parents[1] / 'site_renderer/render.py').read_text()
        ordered = ['guided.generate_from_bundle(', 'guided_locales.generate_from_bundle(', "site/'guided','--canonical-url'", "'finalize_translation_reader.py'", "'finalize_guided_locales.py'", "'check_public_url_boundary.py'"]
        self.assertEqual([text.index(token) for token in ordered], sorted(text.index(token) for token in ordered))

    def test_japanese_guided_routes_are_verified_without_localized_graph(self):
        text=WORKFLOW.read_text()
        self.assertIn('scripts/check_bundle_reader.py',text)
        reader=(ROOT/'scripts/check_bundle_reader.py').read_text()
        self.assertIn('ja/guided/graph.json',reader)
        renderer=(ROOT/'site_renderer/render.py').read_text()
        self.assertIn("bundle/'guided-locales.json'",renderer)
        self.assertIn("build/'guided-locale-publication.json'",renderer)


if __name__ == "__main__":
    unittest.main()
