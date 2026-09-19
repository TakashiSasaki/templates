import json
from pathlib import Path
import tempfile
import unittest

from publication_bundle.contract import BundleError
from site_renderer.progressive_discovery import GENERATED_MARKER, project, validate_generated


ROOT = Path(__file__).resolve().parents[1]


def source():
    return json.loads((ROOT / 'progressive-discovery.json').read_text())


def catalog():
    return json.loads((ROOT / "docs/publication-catalog.json").read_text())


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
        {'publication': 'site', 'document': 'portal-home', 'destination': 'index.md',
         'source': 'docs/landing.md', 'slot': True},
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
        first = project(source(), graph(), documents(), site_catalog=catalog())
        second = project(source(), graph(), documents(), site_catalog=catalog())
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

    def test_missing_site_catalog_fails_closed(self):
        with self.assertRaisesRegex(BundleError, 'Site route/catalog'):
            project(source(), graph(), documents())

    def test_source_path_cannot_be_used_as_a_public_entry(self):
        invalid = source()
        invalid['sections'][0]['entries'][0] = {
            'label': 'bad',
            'source': 'docs/maintainer-onboarding.md',
            'description': 'bad',
        }
        with self.assertRaises(BundleError):
            project(invalid, graph(), documents())

    def test_site_owned_document_does_not_require_a_bundle_slot(self):
        from site_renderer.progressive_discovery import extend_site_documents
        historical = [documents()[0]]
        projected = project(source(), graph(), historical, site_catalog=catalog())
        self.assertIn('(/maintain/site/maintainer-onboarding/)', projected)
        extended = extend_site_documents(ROOT, historical)
        self.assertTrue(any(d['source'] == 'docs/maintainer-onboarding.md' for d in extended))
        self.assertEqual(historical, [documents()[0]])

    def test_site_route_absence_or_malformed_route_is_rejected(self):
        for value in (None, '../escape.md', '/absolute.md', 'bad.html'):
            invalid = source()
            if value is None:
                invalid['site_routes'].pop('site-maintainer-onboarding')
            else:
                invalid['site_routes']['site-maintainer-onboarding'] = value
            with self.subTest(value=value), self.assertRaises(BundleError):
                project(invalid, graph(), [], site_catalog=catalog())

    def test_provider_document_still_requires_selected_bundle_identity(self):
        configured = source()
        configured['sections'][0]['entries'].append({
            'label': 'Provider', 'description': 'Provider-owned documentation.',
            'document': {'publication': 'policy', 'document': 'guide'}})
        provider = {'publication': 'policy', 'document': 'guide', 'destination': 'policy/guide.md'}
        self.assertIn('(/policy/guide/)', project(configured, graph(), [provider], site_catalog=catalog()))
        with self.assertRaisesRegex(BundleError, 'absent from the selected Bundle'):
            project(configured, graph(), [], site_catalog=catalog())

    def test_generated_freshness_detects_marker_preserving_edit(self):
        expected = project(source(), graph(), [], site_catalog=catalog())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'index.md'
            path.write_text(expected.replace('Reader home', 'Stale home'))
            with self.assertRaisesRegex(BundleError, 'stale'):
                validate_generated(path, expected=expected)

    def test_selected_historical_bundle_keeps_site_ownership(self):
        from site_renderer.progressive_discovery import extend_site_documents
        fixture = json.loads((ROOT / 'tests/fixtures/progressive-discovery/historical-site-slots.json').read_text())
        self.assertEqual(fixture['bundle_identity'], '43d0fda160cf9d596fa9596b476e1dcc2a3322e9bf2284d0bfa253cc9a393edb')
        original = fixture['documents']
        effective = extend_site_documents(ROOT, original)
        self.assertEqual(len(effective), len(original) + 1)
        self.assertEqual(effective[-1]['document'], 'site-maintainer-onboarding')
        self.assertIn('(/maintain/publication/integrated-publication/)',
                      project(source(), graph(), original, site_catalog=catalog()))

    def test_local_route_cannot_replace_provider_content(self):
        from site_renderer.progressive_discovery import extend_site_documents
        occupied = [{'publication': 'policy', 'document': 'foreign', 'slot': False,
                     'source': 'README.md', 'destination': 'maintain/site/maintainer-onboarding.md'}]
        with self.assertRaisesRegex(BundleError, 'collision'):
            extend_site_documents(ROOT, occupied)

    def test_public_hrefs_reject_all_dot_segment_boundaries(self):
        for href in ('/a//../x', '/a//./x', '/a//..', '/a//b', '/../x', '/./x', '/foo/..', '/foo/.', '/%2e%2e/x', '/foo/%2E', '/foo\\bar'):
            configured = source()
            configured['sections'][0]['entries'][0] = {'label': 'Bad', 'description': 'Bad.', 'href': href}
            with self.subTest(href=href), self.assertRaises(BundleError):
                project(configured, graph(), [], site_catalog=catalog())

    def test_duplicate_section_titles_keep_entries_in_their_own_section(self):
        configured = source()
        configured['sections'] = [
            {'title': 'Same', 'entries': [{'label': 'First', 'description': 'First route.', 'href': '/first/'}]},
            {'title': 'Same', 'entries': [{'label': 'Second', 'description': 'Second route.', 'href': '/second/'}]},
        ]
        text = project(configured, graph(), [], site_catalog=catalog())
        sections = text.split('## Same\n')[1:]
        self.assertEqual(2, len(sections))
        self.assertIn('(/first/)', sections[0])
        self.assertNotIn('(/second/)', sections[0])
        self.assertIn('(/second/)', sections[1])
        self.assertNotIn('(/first/)', sections[1])

    def test_prose_and_destination_cannot_inject_undeclared_markdown_links(self):
        from html.parser import HTMLParser
        import markdown
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.hrefs = []
                self.images = []
            def handle_starttag(self, tag, attrs):
                if tag == 'a': self.hrefs.append(dict(attrs).get('href'))
                if tag == 'img': self.images.append(dict(attrs))
        configured = source()
        payload = 'normal\n- [undeclared](https://example.com)<img src=x>'
        configured['title'] = payload
        configured['sections'] = [{'title': payload, 'entries': [
            {'label': payload, 'description': payload, 'href': '/a)[undeclared](/other'},
        ]}]
        for label in configured['provider_labels'].values():
            label.update(label=payload, description=payload)
        text = project(configured, graph(), [], site_catalog=catalog())
        parsed = Links()
        parsed.feed(markdown.markdown(text))
        self.assertEqual(['/a%29%5Bundeclared%5D%28/other', '/guided/modeling/', '/guided/composition/', '/guided/policy/'], parsed.hrefs)
        self.assertEqual([], parsed.images)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'index.md'
            path.write_text(text)
            validate_generated(path)
