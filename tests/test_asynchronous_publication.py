"""The publication contract admits new providers and never needs a Site checkout."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from integration import producer
from integration.qualification import qualify
from publication_bundle.contract import BundleError, read_json, validate
from scripts.publish import load_sources, resolve_sources, verify_independence

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def repository(root, title='Example'):
    root.mkdir()
    git(root, 'init', '-q')
    git(root, 'config', 'user.name', 'Fixture')
    git(root, 'config', 'user.email', 'fixture@example.invalid')
    (root/'docs').mkdir()
    (root/'README.md').write_text('# '+title+'\n\n[Source notes](notes.md)\n')
    (root/'notes.md').write_text('# Not published\n')
    (root/'docs/publication-catalog.json').write_text(json.dumps({'schema_version':3,
        'documents':[{'id':'home','source':'README.md','home':True}], 'assets':[]}))
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'Independent authority')
    return root


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.provider=repository(self.base/'provider')

    def build(self, output):
        check=producer.require_revision
        with patch('integration.producer.require_revision', side_effect=lambda root, revision:
                   None if Path(root)==ROOT else check(root, revision)):
            return qualify(root=ROOT, provider_roots={'additional':self.provider},
                provider_revisions={'additional':git(self.provider,'rev-parse','HEAD')},
                producer_revision=git(ROOT,'rev-parse','HEAD'), output=output)

    def test_plain_new_provider_and_catalog_addition_need_no_presentation_manifest(self):
        output=self.base/'first';manifest=self.build(output)
        self.assertEqual(manifest['schema_version'],5)
        self.assertEqual(set(manifest['providers']),{'additional'})
        self.assertNotIn('navigation.json',manifest['files'])
        self.assertNotIn('reader-navigation-runtime.json',manifest['files'])
        self.assertEqual(read_json(output/'guided-navigation.json')['providers'],[])
        text=(output/'publication/additional/index.md').read_text()
        self.assertIn('/blob/'+manifest['providers']['additional']+'/notes.md',text)
        catalog=read_json(self.provider/'docs/publication-catalog.json')
        catalog['documents'].append({'id':'second','source':'second.md'})
        (self.provider/'second.md').write_text('# Added\n\n[Home](README.md)\n')
        (self.provider/'docs/publication-catalog.json').write_text(json.dumps(catalog))
        git(self.provider,'add','.');git(self.provider,'commit','-qm','Add document')
        self.build(self.base/'second')
        self.assertIn('[Home](index.md)',(self.base/'second/publication/additional/second.md').read_text())
        catalog['documents'].pop()
        (self.provider/'docs/publication-catalog.json').write_text(json.dumps(catalog))
        git(self.provider,'add','.');git(self.provider,'commit','-qm','Remove document')
        self.build(self.base/'third')
        self.assertFalse((self.base/'third/publication/additional/second.md').exists())
        # A later branch head does not invalidate a completed older artifact.
        self.assertEqual(validate(output)['identity'],manifest['identity'])

    def test_branch_discovery_records_one_revision_and_rejects_shared_history(self):
        config=load_sources(ROOT/'publication-sources.json')
        config['publications']={'additional':{'ref':'example'}}
        resolved=resolve_sources(config,{'additional':self.provider})
        old=git(self.provider,'rev-parse','HEAD')
        (self.provider/'README.md').write_text('# New head\n')
        git(self.provider,'add','.');git(self.provider,'commit','-qm','Advance')
        self.assertEqual(resolved['additional'][1],old)
        other=repository(self.base/'other','Distinct authority')
        verify_independence({'one':self.provider,'two':other,'integration':ROOT})
        clone=self.base/'clone'
        subprocess.run(['git','clone','-q',str(self.provider),str(clone)],check=True)
        with self.assertRaisesRegex(BundleError,'histories overlap'):
            verify_independence({'one':self.provider,'clone':clone})

    def test_dirty_provider_and_corrupt_payload_are_rejected(self):
        output=self.base/'bundle';self.build(output)
        (output/'publication/additional/index.md').write_text('corrupt')
        with self.assertRaises(BundleError):validate(output)
        (self.provider/'README.md').write_text('uncommitted')
        with self.assertRaisesRegex(BundleError,'tracked source modifications'):
            self.build(self.base/'dirty')
