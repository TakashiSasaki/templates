"""Bundle v3 publishes stale derivatives without inventing synchronization evidence."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
import unittest
import zipfile
from ci_artifacts.publication_bundle import pack, extract
from publication_bundle.contract import canonical, validate, BundleError
from publication_bundle.authority_content.publish_translations import publish_translations, TranslationPublicationError
from publication_bundle.authority_content.translation_fragment_reconciliation import reconcile_translation_fragments
from tests.test_publication_bundle import finish, translation_fixture, PRODUCER, PROVIDERS


class StaleBundleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / 'bundle'

    def read(self, name):
        return json.loads((self.root / name).read_text())

    def write(self, name, data):
        (self.root / name).write_bytes(canonical(data))

    def translations(self, status='current'):
        self.root = translation_fixture(self.root, status)
        return self.read('translation-availability.json')

    def test_stale_exact_evidence_survives_deterministic_archive_roundtrip(self):
        coverage=self.translations('stale');record=coverage['records'][0]
        self.assertNotEqual(record['canonical_blob_sha'],record['current_blob_sha'])
        first=finish(self.root);self.assertEqual(first['schema_version'],3)
        (self.root/'bundle.json').unlink();self.assertEqual(first,finish(self.root))
        archive=self.root.parent/'bundle.tar';pack(self.root,archive)
        zip_path=self.root.parent/'bundle.zip'
        with zipfile.ZipFile(zip_path,'w') as zipped:zipped.write(archive,'bundle.tar')
        output=self.root.parent/'roundtrip'
        actual=extract(zip_path,output,archive_digest='sha256:'+hashlib.sha256(zip_path.read_bytes()).hexdigest(),identity=first['identity'],producer=PRODUCER['revision'],providers=PROVIDERS)
        self.assertEqual(actual,first)
        self.assertEqual(json.loads((output/'translation-availability.json').read_text()),coverage)
        self.assertEqual((output/'publication/ja/intro.md').read_bytes(),(self.root/'publication/ja/intro.md').read_bytes())
        self.assertEqual(set(record),{'publication','document','language','canonical_source','canonical_destination','status','translation_source','canonical_blob_sha','current_blob_sha'})

    def test_previous_current_only_contract_is_not_silently_accepted(self):
        self.translations('stale');manifest=finish(self.root);manifest['schema_version']=1
        self.write('bundle.json',manifest)
        with self.assertRaises(BundleError):validate(self.root)


class TranslationProducerTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);base=Path(tmp.name)
        self.provider=base/'provider';self.provider.mkdir();self.output=base/'publication';self.output.mkdir()
        (self.provider/'docs').mkdir();(self.provider/'docs/index.md').write_text('# Current English\n')
        self.translated=self.provider/'translations/ja/docs/index.md';self.translated.parent.mkdir(parents=True)
        self.prose='# 日本語\n\n> **参考訳（非正本）:** English is canonical.\n\n本文\n'
        self.translated.write_text(self.prose)
        raw=(self.provider/'docs/index.md').read_bytes();oid=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        self.current_oid=oid
        self.manifest={'schema_version':2,'canonical_language':'en','translations':[{'canonical':'docs/index.md','language':'ja','translation':'translations/ja/docs/index.md','canonical_blob_sha':'e'*40,'surfaces':['reader']}]}
        self.publications={'composition':(self.provider,{'intro':{'source':PurePosixPath('docs/index.md')}},[])}
        self.pages=[{'publication':'composition','document':'intro','destination':PurePosixPath('intro.md')}]

    def publish(self):
        (self.provider/'translations/manifest.json').write_bytes(canonical(self.manifest))
        return publish_translations(self.publications,self.pages,self.output)

    def test_real_publisher_includes_current_and_stale_without_editing_sources(self):
        for status in ('stale','current'):
            with self.subTest(status=status):
                self.manifest['translations'][0]['canonical_blob_sha']='e'*40 if status=='stale' else self.current_oid
                records=self.publish();self.assertEqual(len(records),1);self.assertEqual(records[0].status,status)
                self.assertEqual((self.output/'ja/intro.md').read_text(),self.prose)
                self.assertEqual(self.translated.read_text(),self.prose)
                self.assertEqual(json.loads((self.provider/'translations/manifest.json').read_text()),self.manifest)
                (self.output/'ja/intro.md').unlink()

    def test_staleness_does_not_hide_structural_source_errors(self):
        for defect in ('missing','symlink','notice','surface','unsafe','duplicate'):
            with self.subTest(defect=defect):
                self.setUp()
                if defect=='missing':self.translated.unlink()
                elif defect=='symlink':self.translated.unlink();self.translated.symlink_to(self.provider/'docs/index.md')
                elif defect=='notice':self.translated.write_text('# No authority notice')
                elif defect=='surface':self.manifest['translations'][0]['surfaces']=['invented']
                elif defect=='unsafe':self.manifest['translations'][0]['canonical']='../escape.md'
                else:self.manifest['translations'].append(dict(self.manifest['translations'][0]))
                with self.assertRaises(TranslationPublicationError):self.publish()

    def test_stale_fragment_is_not_reinterpreted_against_new_english(self):
        # The old fragment could refer to either of the two new English sections.
        target=self.provider/'docs/other.md';target.write_text('# Other')
        (self.provider/'docs/index.md').write_text('[A](other.md#new-a) [B](other.md#new-b)')
        self.prose+="\n[旧](other.md#old)\n";self.translated.write_text(self.prose)
        self.publications['composition'][1]['other']={'source':PurePosixPath('docs/other.md')}
        self.pages.append({'publication':'composition','document':'other','destination':PurePosixPath('other.md')})
        records=self.publish();before=(self.output/'ja/intro.md').read_bytes()
        self.assertEqual(reconcile_translation_fragments(self.publications,self.pages,records,self.output),0)
        self.assertEqual((self.output/'ja/intro.md').read_bytes(),before)
        self.assertIn(b'#old',before)
