import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from publication_bundle.graph import (
    GRAPH_SCHEMA_VERSION,
    LEGACY_GRAPH_SCHEMA_VERSION,
    LEGACY_ROOT_INDEX,
    ROOT_INDEX,
    graph_diagnostics,
    load_graph,
    validate_provider_graph,
)
from integration.generate_index_navigation_base import collect_provider_graph


class ProgressiveDiscoveryGraphTests(unittest.TestCase):
    def _provider(self, root_index: str, object_id: str = 'f' * 40):
        return {
            'name': 'composition',
            'revision': 'b' * 40,
            'root_index': root_index,
            'indexes': [
                {
                    'path': root_index,
                    'title': 'Root',
                    'sections': [],
                    'depth': 0,
                    'object_id': object_id,
                }
            ],
            'edges': [],
            'diagnostics': {
                'index_count': 1,
                'edge_count': 0,
                'max_index_depth': 0,
                'cycle_edges': [],
                'multiple_parent_indexes': [],
            },
        }

    def test_current_graph_uses_authority_root_index_and_v2(self):
        provider = self._provider(ROOT_INDEX)
        validate_provider_graph(provider, provider_order=('composition',))
        self.assertEqual(GRAPH_SCHEMA_VERSION, 2)
        self.assertEqual(ROOT_INDEX, 'index.md')
        self.assertEqual(graph_diagnostics(provider['indexes'], provider['edges']), provider['diagnostics'])

    def test_legacy_graph_remains_readable_with_its_historical_root(self):
        provider = self._provider(LEGACY_ROOT_INDEX)
        validate_provider_graph(
            provider,
            provider_order=('composition',),
            root_index=LEGACY_ROOT_INDEX,
        )
        self.assertEqual(LEGACY_GRAPH_SCHEMA_VERSION, 1)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'guided-navigation.json'
            path.write_text(
                json.dumps({
                    'schema_version': LEGACY_GRAPH_SCHEMA_VERSION,
                    'repository': 'TakashiSasaki/templates',
                    'providers': [provider],
                }),
                encoding='utf-8',
            )
            self.assertEqual(
                load_graph(path, provider_order=('composition',))['schema_version'],
                LEGACY_GRAPH_SCHEMA_VERSION,
            )

    def test_generator_binds_the_new_root_and_git_blob_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run(
                ['git', '-C', str(root), 'config', 'user.email', 'test@example.invalid'],
                check=True,
            )
            subprocess.run(
                ['git', '-C', str(root), 'config', 'user.name', 'test'],
                check=True,
            )
            (root / 'index.md').write_text(
                '# Provider root\n\n## Start\n\n- [Documentation](docs/index.md) - Provider documents.\n',
                encoding='utf-8',
            )
            (root / 'docs').mkdir()
            (root / 'docs/index.md').write_text('# Documentation\n', encoding='utf-8')
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(root), 'commit', '-qm', 'fixture'], check=True)

            graph = collect_provider_graph('composition', root)
            root_record = next(item for item in graph['indexes'] if item['path'] == ROOT_INDEX)
            blob = subprocess.check_output(
                ['git', '-C', str(root), 'rev-parse', 'HEAD:index.md'],
                text=True,
            ).strip()
            self.assertEqual(graph['root_index'], ROOT_INDEX)
            self.assertEqual(root_record['object_id'], blob)
            self.assertEqual(graph['revision'], subprocess.check_output(
                ['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True
            ).strip())
