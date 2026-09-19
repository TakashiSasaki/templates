"""Adversarial checks of the public, implementation-independent Bundle contract."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from publication_bundle.contract import BundleError, MODELS, canonical, digest, seal, validate
from publication_bundle.paths import audience_routes

PRODUCER={'authority':'integration','revision':'a'*40}
PROVIDERS={'composition':'b'*40,'policy':'c'*40}
PROVIDERS_V4={'modeling':'d'*40,'composition':'b'*40,'policy':'c'*40}
REQUIREMENTS_V4=[
    {'provider':provider,'feature':'publication.generic-document.v1','required':True,'fallback':'generic-document'}
    for provider in ('modeling','composition','policy')
]


def fixture(root):
    root.mkdir()
    models={name:{} for name in MODELS}
    models['documents.json']=[{'publication':'composition','document':'intro','source':'docs/index.md','destination':'intro.md','slot':False}]
    models['navigation.json']={'schema_version':1,'navigation':{'use':[{'publication':'composition','document':'intro','destination':'intro.md','title':'Intro'}]},'locale_labels':{'schema_version':1,'canonical_language':'en','locales':[{'language':'ja','labels':[{'id':'intro','canonical':'Intro','localized':'はじめに'},{'id':'use','canonical':'Use templates','localized':'利用'}]}]},'audience_runtime':{'schema_version':1,'audiences':['use'],'documents':{'intro.md':{'destination':'intro.md','key':'composition:intro','audiences':['use'],'primary':'use','is_landing':False,'title':'Intro'}},'routes':audience_routes(['intro.md']),'navigation':{'use':[{'title':'Intro','destination':'intro.md','href':'/intro/'}]},'overviews':{'use':'/intro/'},'landing_destination':'intro.md'}}
    models['guided-locales.json']={'schema_version':1,'canonical_graph_schema_version':2,'canonical_language':'en','locales':[]}
    models['reader-navigation-runtime.json']={'schema_version':1,'canonical_language':'en','locales':[{'language':'ja','labels':{'Intro':'はじめに','Use templates':'利用'},'routes':{}}]}
    models['guided-navigation.json']={'schema_version':2,'repository':'TakashiSasaki/templates','providers':[{'name':k,'revision':v,'root_index':'index.md','indexes':[{'path':'index.md','title':'Intro','sections':[],'depth':0,'object_id':'f'*40}],'edges':[],'diagnostics':{'index_count':1,'edge_count':0,'max_index_depth':0,'cycle_edges':[],'multiple_parent_indexes':[]}} for k,v in PROVIDERS.items()]}
    models['translation-availability.json']={'schema_version':1,'canonical_language':'en','surface':'reader','languages':[],'summary':{'current':0,'stale':0,'missing':0},'by_language':{},'records':[]}
    models['translation-publication.json']={'schema_version':1,'canonical_language':'en','translations':[]}
    models['glossary.json']={'schema_version':1,'repository':'TakashiSasaki/templates','terms':[]}
    models['provenance.json']={'schema_version':1,'producer':PRODUCER,'providers':PROVIDERS}
    for name,value in models.items():(root/name).write_bytes(canonical(value))
    (root/'publication').mkdir();(root/'publication/intro.md').write_text('# Intro\n')
    return root


def declared_publication_paths(root):
    documents = json.loads((root / 'documents.json').read_text())
    paths = {
        'publication/' + document['destination']
        for document in documents
        if not document['slot']
    }
    publication = json.loads((root / 'translation-publication.json').read_text())
    paths.update(
        'publication/' + record['translation_destination']
        for record in publication['translations']
    )
    return paths


def finish(root, expected_publication_paths=None):
    return seal(
        root,
        producer=PRODUCER,
        providers=PROVIDERS,
        configuration_digest='d' * 64,
        expected_publication_paths=(
            declared_publication_paths(root)
            if expected_publication_paths is None
            else expected_publication_paths
        ),
    )


def v4_fixture(root):
    root = fixture(root)
    provenance = json.loads((root / 'provenance.json').read_text())
    provenance['providers'] = PROVIDERS_V4
    (root / 'provenance.json').write_bytes(canonical(provenance))
    graph = json.loads((root / 'guided-navigation.json').read_text())
    templates = {item['name']: item for item in graph['providers']}
    template = graph['providers'][0]
    graph['providers'] = [
        {**templates.get(provider, template), 'name': provider, 'revision': revision}
        for provider, revision in PROVIDERS_V4.items()
    ]
    (root / 'guided-navigation.json').write_bytes(canonical(graph))
    return root


def finish_v4(root):
    return seal(
        root,
        producer=PRODUCER,
        providers=PROVIDERS_V4,
        configuration_digest='d' * 64,
        expected_publication_paths=declared_publication_paths(root),
        schema_version=4,
        requirements=REQUIREMENTS_V4,
    )


def translation_fixture(root, status='current'):
    root = fixture(root)
    canonical_sha = 'b' * 40
    reviewed_sha = canonical_sha if status == 'current' else 'e' * 40
    coverage = {
        'schema_version': 1,
        'canonical_language': 'en',
        'surface': 'reader',
        'languages': ['ja'],
        'summary': {'current': int(status == 'current'), 'stale': int(status == 'stale'), 'missing': 0},
        'by_language': {'ja': {'current': int(status == 'current'), 'stale': int(status == 'stale'), 'missing': 0}},
        'records': [{
            'publication': 'composition', 'document': 'intro', 'language': 'ja',
            'canonical_source': 'docs/index.md', 'canonical_destination': 'intro.md',
            'status': status, 'translation_source': 'translations/ja/docs/index.md',
            'canonical_blob_sha': reviewed_sha, 'current_blob_sha': canonical_sha,
        }],
    }
    publication = {
        'schema_version': 1,
        'canonical_language': 'en',
        'translations': [{
            'publication': 'composition', 'language': 'ja',
            'canonical_destination': 'intro.md', 'translation_destination': 'ja/intro.md',
        }],
    }
    (root / 'translation-availability.json').write_bytes(canonical(coverage))
    (root / 'translation-publication.json').write_bytes(canonical(publication))
    runtime = json.loads((root / 'reader-navigation-runtime.json').read_text())
    runtime['locales'][0]['routes'] = {'/intro/': '/ja/intro/'}
    (root / 'reader-navigation-runtime.json').write_bytes(canonical(runtime))
    (root / 'publication/ja').mkdir()
    (root / 'publication/ja/intro.md').write_text('# Japanese\n')
    return root


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

    def test_v4_carries_provider_bound_requirement_closure(self):
        root = v4_fixture(self.base / 'v4')
        data = finish_v4(root)
        self.assertEqual(data['schema_version'], 4)
        self.assertEqual(data['requirements'], REQUIREMENTS_V4)
        self.assertEqual(data['requirements_digest'], digest(canonical(REQUIREMENTS_V4)))
        self.assertEqual(validate(root)['identity'], data['identity'])

    def test_v4_rejects_legacy_graph_but_historical_bundle_accepts_it(self):
        for version in (3, 4):
            with self.subTest(version=version):
                root = (v4_fixture if version == 4 else fixture)(self.base / str(version))
                graph = json.loads((root / 'guided-navigation.json').read_text())
                graph['schema_version'] = 1
                for provider in graph['providers']:
                    provider['root_index'] = 'docs/index.md'
                    provider['indexes'][0]['path'] = 'docs/index.md'
                (root / 'guided-navigation.json').write_bytes(canonical(graph))
                locales = json.loads((root / 'guided-locales.json').read_text())
                locales['canonical_graph_schema_version'] = 1
                (root / 'guided-locales.json').write_bytes(canonical(locales))
                if version == 4:
                    with self.assertRaisesRegex(BundleError, 'requires guided graph schema v2'):
                        finish_v4(root)
                    with self.assertRaisesRegex(BundleError, 'requires guided graph schema v2'):
                        validate(root)
                else:
                    finish(root)
                    self.assertEqual(validate(root)['schema_version'], 3)

    def test_v4_requirement_identity_or_provider_binding_fails_closed(self):
        for mutation in ('digest', 'provider'):
            with self.subTest(mutation=mutation):
                root = v4_fixture(self.base / mutation)
                finish_v4(root)
                data = json.loads((root / 'bundle.json').read_text())
                if mutation == 'digest':
                    data['requirements_digest'] = 'e' * 64
                else:
                    data['requirements'][0]['provider'] = 'not-in-tuple'
                    data['requirements_digest'] = digest(canonical(data['requirements']))
                (root / 'bundle.json').write_bytes(canonical(data))
                with self.assertRaises(BundleError):
                    validate(root)

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
            elif file=='guided-navigation.json':data['providers'][0]['revision']='f'*40
            (root/file).write_bytes(canonical(data))
            with self.assertRaises(BundleError):finish(root)

    def test_repository_browser_payload_is_not_a_bundle_model(self):
        self.assertNotIn('provider-repositories.json', MODELS)
        root = fixture(self.base / 'bundle')
        finish(root)
        self.assertFalse((root / 'provider-repositories.json').exists())
        self.assertNotIn('provider-repositories.json', json.loads((root / 'bundle.json').read_text())['files'])

    def test_semantic_source_identity_and_navigation_are_allowed(self):
        root = fixture(self.base / 'semantic')
        documents = json.loads((root / 'documents.json').read_text())
        documents[0]['source'] = 'docs/index.md'
        (root / 'documents.json').write_bytes(canonical(documents))
        finish(root)

    def test_publication_json_is_not_content_scanned(self):
        root = fixture(self.base / 'publication-json')
        (root / 'publication' / 'asset.json').write_bytes(canonical({
            'source_text': 'ordinary publication data',
            'preview': {'entries': ['published']},
        }))
        finish(root, declared_publication_paths(root) | {'publication/asset.json'})

    def test_undeclared_publication_sidecar_is_rejected_before_sealing(self):
        root = fixture(self.base / 'publication-sidecar')
        (root / 'publication' / 'renamed-source.bin').write_bytes(b'opaque source corpus')
        with self.assertRaisesRegex(BundleError, 'publication output closure mismatch'):
            finish(root)

    def test_undeclared_json_sidecar_is_rejected_before_sealing(self):
        root = fixture(self.base / 'publication-json-sidecar')
        (root / 'publication' / 'asset.json').write_bytes(b'{"ok": true}\n')
        with self.assertRaisesRegex(BundleError, 'publication output closure mismatch'):
            finish(root)

    def test_renamed_source_corpus_is_rejected_by_path_closure(self):
        root = fixture(self.base / 'publication-renamed-corpus')
        (root / 'publication' / 'harmless.dat').write_bytes(b'provider source corpus')
        with self.assertRaisesRegex(BundleError, 'publication output closure mismatch'):
            finish(root)

    def test_missing_declared_publication_output_is_rejected(self):
        root = fixture(self.base / 'publication-missing')
        expected = declared_publication_paths(root) | {'publication/declared.json'}
        with self.assertRaisesRegex(BundleError, 'publication output closure mismatch'):
            finish(root, expected)

    def test_publication_inventory_is_exactly_the_qualified_set(self):
        root = fixture(self.base / 'publication-exact')
        expected = declared_publication_paths(root)
        data = finish(root, expected)
        self.assertEqual(
            {path for path in data['files'] if path.startswith('publication/')},
            expected,
        )

    def test_translation_projection_validates_without_provider_sources(self):
        root = translation_fixture(self.base / 'translation')
        finish(root)
        publication = json.loads((root / 'translation-publication.json').read_text())
        publication['translations'][0]['translation_destination'] = 'intro.md'
        (root / 'translation-publication.json').write_bytes(canonical(publication))
        with self.assertRaises(BundleError):
            finish(root)

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
