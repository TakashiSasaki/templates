import json
import copy
from jsonschema import Draft202012Validator, ValidationError
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


    def test_source_matches_schema_and_site_catalog(self):
        source = json.loads((ROOT / 'progressive-discovery.json').read_text())
        schema = json.loads((ROOT / 'schemas/progressive-discovery.schema.json').read_text())
        Draft202012Validator(schema).validate(source)
        identities = {d['id'] for d in json.loads((ROOT / 'docs/publication-catalog.json').read_text())['documents']}
        for section in source['sections']:
            for entry in section['entries']:
                if entry.get('document', {}).get('publication') == 'site':
                    self.assertIn(entry['document']['document'], identities)

    def test_schema_rejects_ambiguous_entries_and_noncanonical_hrefs(self):
        source = json.loads((ROOT / 'progressive-discovery.json').read_text())
        validator = Draft202012Validator(json.loads((ROOT / 'schemas/progressive-discovery.schema.json').read_text()))
        for href in ('/a//../secret', '/a//./page', '/a//..', '/a//b', '/../secret', '/./page', '/docs/..', '/docs/.', '/%2e%2e/secret', '/a/%2E', '//host/path', '/a\\b'):
            value = copy.deepcopy(source)
            value['sections'][0]['entries'][0] = {'label': 'Route', 'description': 'Route.', 'href': href}
            with self.subTest(href=href), self.assertRaises(ValidationError):
                validator.validate(value)
        value = copy.deepcopy(source)
        value['unknown'] = True
        with self.assertRaises(ValidationError): validator.validate(value)
        value = copy.deepcopy(source)
        value['sections'][0]['entries'][0].update(href='/', document={'publication': 'site', 'document': 'portal-home'})
        with self.assertRaises(ValidationError): validator.validate(value)
