"""Adversarial checks of the public, implementation-independent Bundle contract."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from publication_bundle.contract import BundleError, MODELS, canonical, digest, seal, validate

PRODUCER={'authority':'site-internal-integration','revision':'a'*40}
PROVIDERS={'composition':'b'*40,'policy':'c'*40}


def fixture(root):
    root.mkdir()
    models={name:{} for name in MODELS}
    models['documents.json']=[{'publication':'composition','document':'intro','source':'docs/index.md','destination':'intro.md','slot':False}]
    models['navigation.json']={'navigation':{'use':[{'publication':'composition','document':'intro','destination':'intro.md'}]}}
    models['provider-repositories.json']={k:{'revision':v,'entries':[],'browser':[],'previews':[],'published':({'docs/index.md':'intro.md'} if k=='composition' else {})} for k,v in PROVIDERS.items()}
    models['guided-navigation.json']={'schema_version':1,'repository':'TakashiSasaki/templates','providers':[{'name':k,'revision':v,'root_index':'docs/index.md','indexes':[{'path':'docs/index.md','title':'Intro','sections':[],'depth':0,'object_id':'f'*40}],'edges':[],'diagnostics':{'index_count':1,'edge_count':0,'max_index_depth':0}} for k,v in PROVIDERS.items()]}
    models['translation-availability.json']={'schema_version':1,'canonical_language':'en','surface':'reader','languages':[],'summary':{'current':0,'stale':0,'missing':0},'by_language':{},'records':[]}
    models['translation-publication.json']={'schema_version':1,'canonical_language':'en','translations':[]}
    models['glossary.json']={'schema_version':1,'repository':'TakashiSasaki/templates','terms':[]}
    models['provenance.json']={'schema_version':1,'producer':PRODUCER,'providers':PROVIDERS}
    for name,value in models.items():(root/name).write_bytes(canonical(value))
    (root/'publication').mkdir();(root/'publication/intro.md').write_text('# Intro\n')
    return root


def finish(root):return seal(root,producer=PRODUCER,providers=PROVIDERS,configuration_digest='d'*64)


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
        for file in ('provenance.json','guided-navigation.json','provider-repositories.json'):
            root=fixture(self.base/file)
            data=json.loads((root/file).read_text())
            if file=='provenance.json':data['providers']['policy']='f'*40
            elif file=='guided-navigation.json':data['providers'][0]['revision']='f'*40
            else:data['policy']['revision']='f'*40
            (root/file).write_bytes(canonical(data))
            with self.assertRaises(BundleError):finish(root)

    def test_semantic_navigation_closure(self):
        root=fixture(self.base/'bundle')
        (root/'navigation.json').write_bytes(canonical({'navigation':{'use':[{'publication':'policy','document':'absent','destination':'absent.md'}]}}))
        with self.assertRaises(BundleError):finish(root)
