import json
from pathlib import Path
import tempfile
import unittest

from publication_bundle.contract import BundleError
from site_renderer.progressive_discovery import GENERATED_MARKER, project, validate_generated


ROOT = Path(__file__).resolve().parents[1]


def source():
    return json.loads((ROOT / 'progressive-discovery.json').read_text())


def graph():
    return {
        'schema_version': 2,
        'repository': 'TakashiSasaki/templates',
        'providers': [
            {'name': 'modeling', 'root_index': 'index.md'},
            {'name': 'composition', 'root_index': 'index.md'},
            {'name': 'policy', 'root_index': 'index.md'},
        ],
    }


def documents():
    return [
        {'publication': 'site', 'document': 'portal-home', 'destination': 'index.md'},
        {
            'publication': 'site',
            'document': 'site-maintainer-onboarding',
            'destination': 'maintain/site/maintainer-onboarding.md',
        },
        {
            'publication': 'site',
            'document': 'site-integrated-publication',
            'destination': 'maintain/site/publication.md',
        },
        {
            'publication': 'site',
            'document': 'site-site-maintenance',
            'destination': 'maintain/site/maintenance.md',
        },
    ]


class ProgressiveDiscoveryProjectionTests(unittest.TestCase):
    def test_projection_is_deterministic_and_uses_deployed_namespaces(self):
        first = project(source(), graph(), documents())
        second = project(source(), graph(), documents())
        self.assertEqual(first, second)
        self.assertIn(GENERATED_MARKER, first)
        self.assertIn('(/maintain/site/maintainer-onboarding/)', first)
        self.assertIn('(/guided/modeling/)', first)
        self.assertIn('(/guided/composition/)', first)
        self.assertIn('(/guided/policy/)', first)
        self.assertNotIn('docs/maintainer-onboarding.md', first)
        self.assertNotIn('root_index', first)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'index.md'
            path.write_text(first, encoding='utf-8')
            validate_generated(path)

    def test_missing_bundle_document_fails_closed(self):
        incomplete = [documents()[0]]
        with self.assertRaisesRegex(BundleError, 'absent from the selected Bundle'):
            project(source(), graph(), incomplete)

    def test_source_path_cannot_be_used_as_a_public_entry(self):
        invalid = source()
        invalid['sections'][0]['entries'][0] = {
            'label': 'bad',
            'source': 'docs/maintainer-onboarding.md',
            'description': 'bad',
        }
        with self.assertRaises(BundleError):
            project(invalid, graph(), documents())
