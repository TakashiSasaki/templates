"""Availability must be derived from authenticated authority-owned declarations."""
import copy
from publication_bundle.contract import BundleError, canonical
from publication_bundle.source_models import raw_path
import unittest
from tests import test_bundle_review_invariants as fixtures
from tests.test_bundle_review_invariants import add_source
from tests.test_publication_bundle import finish, PROVIDERS
from publication_bundle.paths import audience_routes


class ManifestClosureTests(unittest.TestCase):
    setUp = fixtures.BundleReviewInvariants.setUp
    read = fixtures.BundleReviewInvariants.read
    write = fixtures.BundleReviewInvariants.write
    fresh_bundle = fixtures.BundleReviewInvariants.fresh_bundle
    translations = fixtures.BundleReviewInvariants.translations
    def replace_manifest(self, transform, provider='composition'):
        models=self.read('provider-repositories.json');model=models[provider]
        row=next(r for r in model['browser'] if raw_path(r['path'])==b'translations/manifest.json')
        import json
        manifest=json.loads(row['text']);transform(manifest)
        for field in ('entries','browser','previews'):
            model[field]=[r for r in model[field] if raw_path(r['path'])!=b'translations/manifest.json']
        add_source(model,'translations/manifest.json',canonical(manifest),provider)
        self.write('provider-repositories.json',models)

    def test_self_declared_availability_cannot_hide_or_invent_declarations(self):
        for mutation in ('empty','omit','invent','forged-reviewed','wrong-path','wrong-provider','false-missing'):
            with self.subTest(mutation=mutation),self.fresh_bundle():
                coverage=self.translations();r=coverage['records'][0]
                if mutation=='empty':
                    coverage.update(languages=[],records=[],summary={'current':0,'stale':0,'missing':0},by_language={})
                    self.write('translation-publication.json',{'schema_version':1,'canonical_language':'en','translations':[]})
                    runtime=self.read('reader-navigation-runtime.json');runtime['locales'][0]['routes']={};self.write('reader-navigation-runtime.json',runtime)
                elif mutation=='omit':coverage['records']=[]
                elif mutation=='invent':coverage['records'].append({**r,'language':'fr'})
                elif mutation=='forged-reviewed':r.update(canonical_blob_sha='e'*40,status='stale')
                elif mutation=='wrong-path':r['translation_source']='docs/index.md'
                elif mutation=='wrong-provider':r['publication']='policy'
                else:
                    r['status']='missing'
                    for f in ('translation_source','canonical_blob_sha','current_blob_sha'):del r[f]
                self.write('translation-availability.json',coverage)
                with self.assertRaisesRegex(BundleError,'manifest/source identity'):finish(self.root)

    def test_manifest_contract_is_shared_and_fail_closed(self):
        cases={
            'canonical':lambda m:m['translations'][0].update(canonical='docs/absent.md'),
            'translation':lambda m:m['translations'][0].update(translation='docs/index.md'),
            'unsafe':lambda m:m['translations'][0].update(canonical='../docs/index.md'),
            'surface':lambda m:m['translations'][0].update(surfaces=['invented']),
            'language':lambda m:m['translations'][0].update(language='en'),
            'duplicate':lambda m:m['translations'].append(copy.deepcopy(m['translations'][0])),
            'undeclared':lambda m:m.update(translations=[]),
            'reviewed-identity':lambda m:m['translations'][0].update(canonical_blob_sha='e'*40),
            'guided-only':lambda m:m['translations'][0].update(surfaces=['guided']),
        }
        for name,mutation in cases.items():
            with self.subTest(name=name),self.fresh_bundle():
                self.translations();self.replace_manifest(mutation)
                with self.assertRaises(BundleError):finish(self.root)

    def test_manifest_is_bound_to_owning_provider_and_object(self):
        for mutation in ('object','other-provider','symlink','parent-symlink','missing','malformed'):
            with self.subTest(mutation=mutation),self.fresh_bundle():
                self.translations();models=self.read('provider-repositories.json');model=models['composition']
                row=next(r for r in model['browser'] if raw_path(r['path'])==b'translations/manifest.json')
                raw=row['text'].encode()
                if mutation=='object':row['text']='{}'
                else:
                    for field in ('entries','browser','previews'):
                        model[field]=[r for r in model[field] if raw_path(r['path'])!=b'translations/manifest.json']
                    if mutation=='other-provider':add_source(models['policy'],'translations/manifest.json',raw,'policy')
                    elif mutation=='malformed':add_source(model,'translations/manifest.json',b'{"schema_version":2,"schema_version":2}')
                    elif mutation in ('symlink','parent-symlink'):
                        from tests.test_bundle_review_invariants import encoded
                        path=b'translations/manifest.json' if mutation=='symlink' else b'translations'
                        model['entries'].append({'path':encoded(path),'name':encoded(path.rsplit(b'/',1)[-1]),'mode':'120000','kind':'blob','object_id':'f'*40})
                self.write('provider-repositories.json',models)
                with self.assertRaises(BundleError):finish(self.root)

    def test_current_derivative_required_and_stale_derivative_forbidden(self):
        for status in ('current','stale'):
            with self.subTest(status=status),self.fresh_bundle():
                self.translations(status);publication=self.read('translation-publication.json')
                publication['translations']=[] if status=='current' else [{'publication':'composition','language':'ja','canonical_destination':'intro.md','translation_destination':'ja/intro.md'}]
                self.write('translation-publication.json',publication)
                runtime=self.read('reader-navigation-runtime.json');runtime['locales'][0]['routes']={} if status=='current' else {'/intro/':'/ja/intro/'};self.write('reader-navigation-runtime.json',runtime)
                with self.assertRaisesRegex(BundleError,'derivative'):finish(self.root)

    def test_missing_coverage_is_derived_for_undeclared_canonical_page(self):
        self.translations()
        docs=self.read('documents.json');docs.append({**docs[0],'document':'second','source':'docs/second.md','destination':'second.md'});self.write('documents.json',docs)
        (self.root/'publication/second.md').write_text('# Second')
        models=self.read('provider-repositories.json');add_source(models['composition'],'docs/second.md',b'# Second');models['composition']['published']['docs/second.md']='second.md';self.write('provider-repositories.json',models)
        nav=self.read('navigation.json');a=nav['audience_runtime'];a['documents']['second.md']={**a['documents']['intro.md'],'destination':'second.md','key':'composition:second'};a['routes']=audience_routes(['intro.md','second.md']);self.write('navigation.json',nav)
        coverage=self.read('translation-availability.json');coverage['records'].append({'publication':'composition','document':'second','language':'ja','canonical_source':'docs/second.md','canonical_destination':'second.md','status':'missing'})
        coverage['summary']['missing']=1;coverage['by_language']['ja']['missing']=1;self.write('translation-availability.json',coverage)
        finish(self.root)
        (self.root/'bundle.json').unlink()
        coverage['records'].pop();self.write('translation-availability.json',coverage)
        with self.assertRaisesRegex(BundleError,'manifest/source identity'):finish(self.root)
