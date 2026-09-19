from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from publication_bundle.graph import load_graph, IndexNavigationViewerError
from site_renderer.guided import generate_from_bundle
from site_renderer.guided_locales import generate_from_bundle as generate_locales


class GuidedRootRoleTests(unittest.TestCase):
    def test_graph_versions_are_exact_integers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'graph.json'
            for version in (True, False, 1.0, 2.0, '1', '2', None, [], {}):
                with self.subTest(version=version):
                    path.write_text(json.dumps({'schema_version': version, 'repository': 'TakashiSasaki/templates', 'providers': []}))
                    with self.assertRaises(IndexNavigationViewerError):
                        load_graph(path, provider_order=())
            for version in (1, 2):
                path.write_text(json.dumps({'schema_version': version, 'repository': 'TakashiSasaki/templates', 'providers': []}))
                self.assertEqual(load_graph(path, provider_order=())['schema_version'], version)

    def test_current_and_legacy_roots_have_distinct_children_in_both_locales(self):
        for version, root, child, suffix in (
            (2, 'index.md', 'docs/index.md', 'guided/policy/docs/'),
            (1, 'docs/index.md', 'index.md', 'guided/_repository-root/policy/'),
        ):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                indexes = [{'path': p, 'title': title, 'sections': [], 'depth': depth, 'object_id': 'b' * 40}
                           for p, title, depth in [(root, 'Root', 0), (child, 'Child', 1)]]
                edge = {'source': root, 'target': child, 'kind': 'index', 'label': 'Child',
                        'description': 'Descendant index.', 'section': None, 'line': 3,
                        'raw_target': child, 'fragment': None}
                sibling = '_repository-root/index.md'
                indexes.append({'path': sibling, 'title': 'Sibling', 'sections': [], 'depth': 1, 'object_id': 'c' * 40})
                sibling_edge = dict(edge, target=sibling, raw_target=sibling, label='Sibling')
                provider = {'name': 'policy', 'revision': 'a' * 40, 'root_index': root,
                            'indexes': indexes, 'edges': [edge, sibling_edge],
                            'diagnostics': {'index_count': 3, 'edge_count': 2, 'max_index_depth': 1}}
                graph = {'schema_version': version, 'repository': 'TakashiSasaki/templates', 'providers': [provider]}
                overlays = {'ja': {'policy': {p: {'title': 'ルート' if p == root else '子', 'sections': [],
                            'links': [{'label': '子', 'description': '子の索引。'}, {'label': '兄弟', 'description': '兄弟の索引。'}] if p == root else []}
                            for p in (root, child, sibling)}}}
                generate_from_bundle(graph['repository'], graph, {'policy': {}}, output)
                pair_map = output / 'pairs.json'
                generate_locales(graph['repository'], graph, overlays, {}, {'policy': {}}, output, pair_map)
                for locale in ('', 'ja/'):
                    root_page = output / f'{locale}guided/policy/index.html'
                    child_page = output / f'{locale}{suffix}index.html'
                    self.assertTrue(root_page.is_file())
                    self.assertTrue(child_page.is_file())
                    sibling_page = output / f'{locale}guided/policy/_repository-root/index.html'
                    self.assertTrue(sibling_page.is_file())
                    self.assertNotEqual(child_page, sibling_page)
                    self.assertIn(f'href="/{locale}guided/policy/_repository-root/"', root_page.read_text())
                    self.assertIn(f'href="/{locale}{suffix}"', root_page.read_text())
                    self.assertIn(f'href="/{locale}guided/policy/"', child_page.read_text())
                    self.assertIn(f'<code>/{locale}{suffix}</code>', child_page.read_text())
                pairs = json.loads(pair_map.read_text())['pages']
                self.assertTrue(any(p['canonical_path'] == f'{suffix}index.html'
                                    and p['translation_path'] == f'ja/{suffix}index.html' for p in pairs))
