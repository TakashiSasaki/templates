"""Regressions for the three cumulative review findings at Bundle acceptance."""
import base64
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from publication_bundle.contract import BundleError, canonical
from publication_bundle.source_models import blob_sha, validate_sources
from publication_bundle.repository import (decode_browser_text, decode_preview_text,
    viewer_relative_url, source_url, preview_relative_url, github_url, MAX_PREVIEW_BYTES)
from tests.test_publication_bundle import fixture, finish, PROVIDERS

REPOSITORY='TakashiSasaki/templates'


def encoded(path):return {'base64':base64.b64encode(path).decode()}


def add_source(model,path,raw,provider='composition'):
    path=path.encode();oid=blob_sha(raw);revision=model['revision']
    model['entries'].append({'path':encoded(path),'name':encoded(path.rsplit(b'/',1)[-1]),'mode':'100644','kind':'blob','object_id':oid})
    text,reason=decode_browser_text(raw)
    model['browser'].append({'path':encoded(path),'object_id':oid,'size':len(raw),'viewer_url':viewer_relative_url(provider,revision,path),'source_url':source_url(REPOSITORY,revision,path),'viewable':text is not None,'reason':reason,'text':text})
    preview=decode_preview_text(raw)
    if preview is not None:model['previews'].append({'path':encoded(path),'object_id':oid,'text':preview,'relative_url':preview_relative_url(provider,revision,path),'source_url':github_url(REPOSITORY,revision,'blob',path)})
    return oid


class BundleReviewInvariants(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=fixture(Path(self.tmp.name)/'bundle')

    def read(self,name):return json.loads((self.root/name).read_text())
    def write(self,name,data):(self.root/name).write_bytes(canonical(data))

    def translations(self,status='current'):
        models=self.read('provider-repositories.json')
        sha=add_source(models['composition'],'docs/index.md',b'# Intro\n')
        add_source(models['composition'],'translations/ja/index.md','日本語'.encode())
        self.write('provider-repositories.json',models)
        r={'publication':'composition','document':'intro','language':'ja','canonical_source':'docs/index.md','canonical_destination':'intro.md','status':status}
        if status!='missing':r.update(translation_source='translations/ja/index.md',canonical_blob_sha=sha if status=='current' else 'e'*40,current_blob_sha=sha)
        counts={'current':0,'stale':0,'missing':0};counts[status]=1
        coverage={'schema_version':1,'canonical_language':'en','surface':'reader','languages':['ja'],'records':[r],'summary':counts,'by_language':{'ja':counts}}
        self.write('translation-availability.json',coverage)
        publication={'schema_version':1,'canonical_language':'en','translations':[]}
        if status=='current':
            publication['translations']=[{'publication':'composition','language':'ja','canonical_destination':'intro.md','translation_destination':'ja/intro.md'}]
            (self.root/'publication/ja').mkdir();(self.root/'publication/ja/intro.md').write_text('日本語')
        self.write('translation-publication.json',publication)
        # S4 additionally validates the runtime projection, absent in S2 fixtures.
        runtime=self.read('reader-navigation-runtime.json')
        for locale in runtime.get('locales',[]):
            if locale['language']=='ja':locale['routes']={'/intro/':'/ja/intro/'} if status=='current' else {}
        self.write('reader-navigation-runtime.json',runtime)
        return coverage

    def test_valid_provider_graph_and_translation_states(self):
        finish(self.root)
        for status in ('current','stale','missing'):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as tmp:
                saved=self.root;self.root=fixture(Path(tmp)/'bundle')
                self.translations(status);finish(self.root);self.root=saved

    def test_all_nested_provider_graphs_are_validated(self):
        original=self.read('guided-navigation.json')
        for provider in range(2):
            for mutation in ('empty','edge','diagnostics'):
                graph=copy.deepcopy(original);p=graph['providers'][provider]
                if mutation=='empty':p['indexes']=[]
                elif mutation=='edge':p['edges']=[{'source':'docs/unknown/index.md'}]
                else:p['diagnostics']['index_count']=99
                self.write('guided-navigation.json',graph)
                with self.subTest(provider=provider,mutation=mutation),self.assertRaises(BundleError):finish(self.root)

    def test_arbitrary_equal_sha_cannot_manufacture_current(self):
        coverage=self.translations();coverage['records'][0].update(canonical_blob_sha='f'*40,current_blob_sha='f'*40)
        self.write('translation-availability.json',coverage)
        with self.assertRaisesRegex(BundleError,'canonical.*identity'):finish(self.root)

    def test_paths_must_exist_as_regular_sources_in_owning_provider(self):
        self.translations();original=self.read('provider-repositories.json')
        for source in ('docs/index.md','translations/ja/index.md'):
            for mutation in ('missing','other-provider','symlink'):
                models=copy.deepcopy(original);model=models['composition'];p=encoded(source.encode())
                entries=[e for e in model['entries'] if e['path']==p]
                for field in ('entries','browser','previews'):model[field]=[r for r in model[field] if r['path']!=p]
                if mutation=='symlink':model['entries'] += [{**entries[0],'mode':'120000'}]
                elif mutation=='other-provider':add_source(models['policy'],source,b'other owner','policy')
                self.write('provider-repositories.json',models)
                with self.subTest(source=source,mutation=mutation),self.assertRaises(BundleError):finish(self.root)

    def test_stale_cannot_be_published_or_relabelled_current(self):
        coverage=self.translations('stale');coverage['records'][0]['status']='current'
        coverage['summary']={'current':1,'stale':0,'missing':0};coverage['by_language']['ja']=coverage['summary']
        self.write('translation-availability.json',coverage)
        with self.assertRaises(BundleError):finish(self.root)

    def test_exact_preview_eligibility_and_completeness(self):
        model=self.read('provider-repositories.json')['composition']
        for path,raw in [('small.txt',b'hello'),('empty.txt',b''),('limit.txt',b'x'*MAX_PREVIEW_BYTES),('large.txt',b'x'*(MAX_PREVIEW_BYTES+1)),('binary',b'\0'),('invalid',b'\xff'),('control',b'\x01')]:add_source(model,path,raw)
        validate_sources('composition',model,REPOSITORY)
        for previews in ([],model['previews'][:-1],model['previews'][1:],model['previews']+[model['previews'][0]]):
            with self.subTest(count=len(previews)),self.assertRaises(BundleError):validate_sources('composition',{**model,'previews':previews},REPOSITORY)
        extra=copy.deepcopy(model['previews'][0]);extra['path']=encoded(b'binary')
        with self.assertRaises(BundleError):validate_sources('composition',{**model,'previews':model['previews']+[extra]},REPOSITORY)

    def test_preview_aggregate_limits_are_preserved(self):
        model=self.read('provider-repositories.json')['composition'];add_source(model,'file',b'abc')
        with patch('publication_bundle.source_models.MAX_TOTAL_PREVIEW_BYTES',2),self.assertRaises(BundleError):validate_sources('composition',model,REPOSITORY)
        with patch('publication_bundle.source_models.MAX_CANDIDATE_BYTES',2,create=True),self.assertRaises(BundleError):validate_sources('composition',model,REPOSITORY)
