"""Exercise renderer entry-point and import isolation, not only directory names."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class RendererBoundaryTests(unittest.TestCase):
    def test_renderer_imports_without_integration_implementation(self):
        code='''
import importlib.abc
import sys
class DenyIntegration(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'integration' or fullname.startswith('integration.'):
            raise RuntimeError('renderer imported Integration implementation: '+fullname)
sys.meta_path.insert(0,DenyIntegration())
import site_renderer.render
import site_renderer.local_content
import site_renderer.guided_locales
import site_renderer.repository_browser
'''
        result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_renderer_rejects_provider_checkout_escape_arguments(self):
        for argument in ('--composition-root','--policy-root','--publication','--provider'):
            result=subprocess.run([sys.executable,str(ROOT/'scripts/render_publication_bundle.py'),
                '--bundle','unused','--bundle-identity','a'*64,'--site-root',str(ROOT),
                '--output','unused',argument,'forbidden'],capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertIn('unrecognized arguments',result.stderr)

    def test_isolation_qualification_removes_integration_and_requires_renderer_success(self):
        source=(ROOT/'scripts/qualify_bundle_renderer.py').read_text()
        self.assertIn("shutil.rmtree(source/'integration')",source)
        self.assertIn("assert not (root/'composition-source').exists()",source)
        self.assertIn("assert not (root/'policy-source').exists()",source)
        self.assertIn("cwd=root,env=env,check=True",source)
        self.assertIn("output/'site/index.html'",source)

    def test_site_translation_links_use_bundle_provider_availability(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from pathlib import PurePosixPath
        from site_renderer.local_content import fill
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); source=root/'site'; source.mkdir()
            (source/'assets').mkdir(); (source/'index.md').write_text('English')
            docs=root/'docs'; docs.mkdir(); (docs/'ja').mkdir()
            (docs/'ja/provider.md').write_text('Provider translation')
            output=root/'output'; output.mkdir()
            local=SimpleNamespace(language='ja',canonical_destination=PurePosixPath('index.md'),translation_destination=PurePosixPath('ja/index.md'))
            def publish(*args,**kwargs):
                (docs/'ja/index.md').write_text('[Provider](/provider/)')
                return [local]
            providers={'translations':[{'publication':'composition','language':'ja','canonical_destination':'provider.md','translation_destination':'ja/provider.md'}]}
            nav={'locale_labels':{},'navigation':{},'audience_runtime':{'documents':{},'routes':{},'overviews':{}}}
            with patch('site_renderer.local_content.read_entries',return_value=[]), patch('site_renderer.local_content.publish_translations',side_effect=publish), patch('site_renderer.local_content.reconcile_translation_fragments'), patch('site_renderer.local_content.build_reader_coverage',return_value={}), patch('site_renderer.local_content.load_overlays',return_value={}), patch('site_renderer.local_content.build_runtime_map',return_value={}):
                fill(source,docs,[{'slot':True,'document':'home','source':'index.md','destination':'index.md'}],nav,providers,{},output)
            self.assertEqual((docs/'ja/index.md').read_text(),'[Provider](/ja/provider/)')
