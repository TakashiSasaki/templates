"""Adversarial checks of the public, implementation-independent Bundle contract."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from publication_bundle.contract import BundleError, MODELS, canonical, digest
from publication_bundle.paths import audience_routes

from site_renderer.bundle import validate
from tests.bundle_consumer_fixture import fixture,finish as seal_fixture,PRODUCER,PROVIDERS

def finish(root):
    data=seal_fixture(root);validate(root);return data


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)

    def test_same_bytes_have_same_identity_across_roots_and_mtimes(self):
        import os
        a=fixture(self.base/'a');b=fixture(self.base/'b')
        os.utime(b/'publication/intro.md',(1,1))
        self.assertEqual(finish(a),finish(b))

    def test_changed_bytes_change_content_identity(self):
        a=fixture(self.base/'a');b=fixture(self.base/'b')
        (b/'publication/intro.md').write_text('# Changed\n')
        self.assertNotEqual(finish(a)['identity'],finish(b)['identity'])

    def test_payload_corruption_and_unlisted_files_fail(self):
        for mutation in ('modify','add','remove'):
            with self.subTest(mutation=mutation):
                root=fixture(self.base/mutation);finish(root)
                p=root/'publication/intro.md'
                if mutation=='modify':p.write_text('corrupt')
                elif mutation=='remove':p.unlink()
                else:(root/'extra').write_text('unexpected')
                with self.assertRaises(BundleError):validate(root)

    def test_exact_revision_and_identity_expectations(self):
        root=fixture(self.base/'bundle');finish(root)
        for kwargs in ({'expected_identity':'e'*64},{'expected_producer':{**PRODUCER,'revision':'e'*40}},{'expected_providers':{**PROVIDERS,'policy':'e'*40}}):
            with self.subTest(kwargs=kwargs),self.assertRaises(BundleError):validate(root,**kwargs)

    def test_manifest_schema_and_duplicate_json_members_fail(self):
        root=fixture(self.base/'bundle');data=finish(root)
        for value in (b'{"schema_version":1,"schema_version":1}', canonical({**data,'schema_version':True}),canonical({**data,'unexpected':1})):
            (root/'bundle.json').write_bytes(value)
            with self.assertRaises(BundleError):validate(root)

    def test_symlink_and_traversal_fail(self):
        root=fixture(self.base/'bundle');finish(root)
        p=root/'publication/intro.md';p.unlink();p.symlink_to('/etc/hosts')
        with self.assertRaises(BundleError):validate(root)
        from publication_bundle.contract import safe_path
        for path in ('../outside','/absolute','a/../b','a//b','a\\b','.git/config','./a'):
            with self.subTest(path=path),self.assertRaises(BundleError):safe_path(path)

    def test_missing_declared_content_and_required_models_fail(self):
        for relative in ('publication/intro.md','glossary.json'):
            root=fixture(self.base/relative.replace('/','-'))
            (root/relative).unlink()
            with self.assertRaises(BundleError):finish(root)

    def test_duplicate_destinations_and_invalid_slots_fail(self):
        for change in ('duplicate','slot'):
            root=fixture(self.base/change)
            documents=json.loads((root/'documents.json').read_text())
            if change=='duplicate':documents.append({**documents[0],'document':'second'})
            else:documents[0]['slot']=True
            (root/'documents.json').write_bytes(canonical(documents))
            with self.assertRaises(BundleError):finish(root)

    def test_provenance_and_graph_revision_mismatch_fail(self):
        for file in ('provenance.json','guided-navigation.json'):
            root=fixture(self.base/file)
            data=json.loads((root/file).read_text())
            if file=='provenance.json':data['providers']['policy']='f'*40
            else:data['providers'][0]['revision']='f'*40
            (root/file).write_bytes(canonical(data))
            with self.assertRaises(BundleError):finish(root)

    def test_repository_source_corpus_is_not_a_bundle_model(self):
        root=fixture(self.base/'bundle')
        self.assertNotIn('provider-repositories.json', MODELS)
        self.assertFalse((root/'provider-repositories.json').exists())

    def test_semantic_navigation_closure(self):
        root=fixture(self.base/'bundle')
        (root/'navigation.json').write_bytes(canonical({'navigation':{'use':[{'publication':'policy','document':'absent','destination':'absent.md'}]}}))
        with self.assertRaises(BundleError):finish(root)

    def test_secondary_read_models_are_checked_during_qualification(self):
        for name in ('guided-locales.json','reader-navigation-runtime.json','navigation.json'):
            root=fixture(self.base/name)
            model=json.loads((root/name).read_text())
            if name=='guided-locales.json':model['canonical_graph_schema_version']=99
            elif name=='reader-navigation-runtime.json':model['locales'][0]['routes']['/intro/']='/absent/'
            else:model['audience_runtime']['routes']['https://untrusted.example/']='intro.md'
            (root/name).write_bytes(canonical(model))
            with self.subTest(name=name),self.assertRaises(BundleError):finish(root)

    def test_audience_routes_require_every_producer_alias(self):
        for alias in audience_routes(['intro.md']):
            with self.subTest(alias=alias):
                with tempfile.TemporaryDirectory() as temporary:
                    root=fixture(Path(temporary)/'bundle')
                    model=json.loads((root/'navigation.json').read_text())
                    del model['audience_runtime']['routes'][alias]
                    (root/'navigation.json').write_bytes(canonical(model))
                    with self.assertRaisesRegex(BundleError,'route projection'):finish(root)

    def test_audience_routes_reject_extra_and_misbound_aliases(self):
        for mutation in ('extra','wrong-target'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temporary:
                root=fixture(Path(temporary)/'bundle');model=json.loads((root/'navigation.json').read_text())
                if mutation=='extra':model['audience_runtime']['routes']['/intro/index.html']='intro.md'
                else:model['audience_runtime']['routes']['/intro.html']='absent.md'
                (root/'navigation.json').write_bytes(canonical(model))
                with self.assertRaisesRegex(BundleError,'route projection'):finish(root)

    def test_shared_alias_projection_preserves_root_directory_and_file_rules(self):
        self.assertEqual(set(audience_routes(['index.md'])),{'index.md','/index.md','/','','/index.html','index.html'})
        self.assertEqual(set(audience_routes(['web/index.md'])),{'web/index.md','/web/index.md','/web/','web','web/','/web/index.html'})
        self.assertEqual(set(audience_routes(['guide.md'])),{'guide.md','/guide.md','/guide/','/guide','/guide.html'})
        with self.assertRaisesRegex(ValueError,'route collision'):audience_routes(['guide.md','guide/index.md'])
