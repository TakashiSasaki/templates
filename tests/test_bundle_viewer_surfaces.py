"""Guided navigation regressions consume the semantic graph without providers."""
import tempfile,unittest
from pathlib import Path
from site_renderer import guided
from tests.test_index_navigation_viewer_hardening import provider_graph,edge

class BundleViewerSurfaceTests(unittest.TestCase):
 def test_generic_provider_graph_renders_published_source_external_and_nested_links(self):
  provider=provider_graph();provider['name']='example'
  provider['edges']=[edge('docs/architecture/index.md',kind='index'),edge('docs/page.md',kind='file'),edge('notes.txt',kind='file'),edge('https://example.com/spec#part')]
  provider['edges'][2]['label']='<script>alert(1)</script>'
  provider['diagnostics']['edge_count']=4
  graph={'schema_version':1,'repository':'owner/repo','providers':[provider]}
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);guided.generate_from_bundle('owner/repo',graph,{'example':{'docs/page.md':'example/page.md'}},root)
   page=(root/'guided/example/index.html').read_text()
   self.assertIn('href="/example/page/"',page)
   self.assertIn('href="/guided/example/docs/architecture/"',page)
   self.assertIn('/blob/'+provider['revision']+'/notes.txt',page)
   self.assertIn('href="https://example.com/spec#part"',page)
   self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',page)
   self.assertNotIn('<script>alert(1)</script>',page)
   self.assertTrue((root/'guided/example/docs/architecture/index.html').exists())
 def test_failed_guided_output_has_no_partial_tree(self):
  from unittest.mock import patch
  graph={'schema_version':1,'repository':'owner/repo','providers':[provider_graph()]}
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch.object(Path,'write_text',side_effect=OSError('disk full')),self.assertRaises(OSError):
    guided.generate_from_bundle('owner/repo',graph,{'skill':{}},root)
   self.assertFalse((root/'guided').exists())
