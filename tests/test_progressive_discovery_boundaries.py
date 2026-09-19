import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProgressiveDiscoveryBoundaryTests(unittest.TestCase):
    def test_adapter_names_local_inventories_and_semantic_surfaces(self):
        adapter = json.loads((ROOT / '.progressive-discovery.json').read_text())
        self.assertEqual(adapter['root_index'], 'index.md')
        self.assertEqual(adapter['authored_boundaries'], ['docs', 'contracts'])
        self.assertIn('publication-sources.json', adapter['authoritative_inventories'])
        self.assertEqual(
            adapter['surface_boundaries']['discovery-graph']['consumer'],
            'guided-navigation.json',
        )
        self.assertIn('publication', adapter['explicit_exclusions'])

    def test_authored_boundaries_are_reachable_from_root_index(self):
        root = (ROOT / 'index.md').read_text()
        docs = (ROOT / 'docs/index.md').read_text()
        contracts = (ROOT / 'contracts/index.md').read_text()
        self.assertIn('(docs/index.md)', root)
        self.assertIn('(contracts/index.md)', root)
        self.assertIn('(../contracts/index.md)', docs)
        for text in (root, docs, contracts):
            self.assertTrue(text.startswith('# '))
            self.assertNotIn('git SHA', text)
            self.assertNotIn('provenance', text.lower())

    def test_hashed_producer_configuration_is_in_the_discovery_contract(self):
        from integration.producer import CONFIGURATION_FILES
        adapter = json.loads((ROOT / '.progressive-discovery.json').read_text())
        self.assertTrue(set(CONFIGURATION_FILES).issubset(adapter['authoritative_inventories']))
        self.assertTrue(set(CONFIGURATION_FILES).issubset(adapter.get('expected_documents', [])))
        root = (ROOT / 'index.md').read_text()
        for source in ('reader-navigation-locales.json', 'integration/site-slots.json'):
            self.assertIn(f']({source})', root)
