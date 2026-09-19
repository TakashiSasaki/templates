import json
from pathlib import Path
import unittest
import yaml


ROOT = Path(__file__).resolve().parents[1]


class ProgressiveDiscoverySourceTests(unittest.TestCase):
    def test_site_explicitly_selects_the_immutable_policy_skill(self):
        policy = yaml.safe_load((ROOT / '.agent-policy.yml').read_text())
        self.assertRegex(policy['toolchain']['revision'], r'^[0-9a-f]{40}$')
        self.assertIn('progressive-discovery', policy['contexts']['default']['profiles'])
        self.assertIn('maintain-progressive-discovery', policy['skills']['enabled'])
        lock = yaml.safe_load((ROOT / '.agent-policy.lock').read_text())
        self.assertEqual(policy['toolchain'], lock['toolchain'])
        self.assertIn('.agents/skills/maintain-progressive-discovery/SKILL.md', lock['outputs'])

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
