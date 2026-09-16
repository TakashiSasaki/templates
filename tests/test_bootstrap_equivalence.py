import copy
import json
from pathlib import Path
import tempfile
import unittest
from integration.bootstrap import compare
from publication_bundle.contract import BundleError, canonical, digest
from tests.test_publication_bundle import fixture,finish,PROVIDERS

class BootstrapEquivalenceTests(unittest.TestCase):
    def test_payload_drift_cannot_hide_behind_regenerated_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=fixture(Path(tmp)/'bundle');manifest=finish(root)
            reference={'providers':PROVIDERS,'equivalent_files':{p:r for p,r in manifest['files'].items() if p not in {'glossary.json','provenance.json'}},'provider_glossary_sha256':digest(canonical([])),'integration_glossary_ids':[],'site_bundle_identity':'f'*64,'permitted_differences':[]}
            compare(root,reference)
            for change in ('provider','glossary','own-inventory'):
                altered=copy.deepcopy(reference)
                if change=='provider':altered['providers']['policy']='e'*40
                elif change=='glossary':altered['provider_glossary_sha256']='e'*64
                else:altered['integration_glossary_ids']=['invented']
                with self.assertRaises(BundleError):compare(root,altered)
            (root/'bundle.json').unlink();(root/'publication/intro.md').write_text('changed provider text')
            changed=finish(root);self.assertNotEqual(changed['identity'],manifest['identity'])
            with self.assertRaisesRegex(BundleError,'payload drift'):compare(root,reference)
