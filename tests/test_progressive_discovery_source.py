import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProgressiveDiscoverySourceTests(unittest.TestCase):
    def test_adapter_declares_site_owned_source_and_bundle_projection(self):
        adapter = json.loads((ROOT / '.progressive-discovery.json').read_text())
        self.assertEqual(adapter['root_index'], 'index.md')
        self.assertEqual(adapter['authored_boundaries'], ['docs', 'contracts'])
        self.assertIn('progressive-discovery.json', adapter['authoritative_inventories'])
        self.assertEqual(
            adapter['surface_boundaries']['integration-read-model']['consumer'],
            'generated site/index.md',
        )

    def test_source_uses_public_routes_or_document_identity_not_source_paths(self):
        source = json.loads((ROOT / 'progressive-discovery.json').read_text())
        self.assertEqual(source['schema_version'], 1)
        for section in source['sections']:
            for entry in section['entries']:
                self.assertTrue('href' in entry or 'document' in entry)
                self.assertNotIn('source', entry)
                self.assertNotIn('path', entry)
                if 'href' in entry:
                    self.assertTrue(entry['href'].startswith('/'))
        self.assertEqual(
            set(source['provider_labels']), {'modeling', 'composition', 'policy'}
        )

