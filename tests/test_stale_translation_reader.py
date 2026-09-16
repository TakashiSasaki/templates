"""Availability is supplied upstream; Site only renders its reader consequences."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from finalize_translation_reader import finalize,TranslationReaderError
from tests.test_translation_reader import HTML

class StaleTranslationReaderTests(unittest.TestCase):
    def fixture(self,root,status='stale'):
        site=root/'site';site.mkdir()
        for route in ('policy/cli','ja/policy/cli','policy/english-only'):
            if status=='missing' and route.startswith('ja/'):continue
            p=site/route/'index.html';p.parent.mkdir(parents=True);p.write_text(HTML.format(title='Document',body='Provider-owned prose'))
        row={'publication':'policy','language':'ja','canonical_destination':'policy/cli.md','translation_destination':'ja/policy/cli.md'}
        mapping=root/'map.json';mapping.write_text(json.dumps({'schema_version':1,'canonical_language':'en','translations':[] if status=='missing' else [row]}))
        availability=root/'availability.json';availability.write_text(json.dumps({'schema_version':1,'canonical_language':'en','surface':'reader','records':[{'publication':'policy','language':'ja','canonical_destination':'policy/cli.md','status':status,'canonical_blob_sha':'a'*40,'current_blob_sha':'b'*40}]}))
        (root/'inventory.json').write_text(json.dumps({'schema_version':1,'coverage':[{'publication':'policy','language':'ja','canonical_destination':'policy/cli.md'}]}))
        return site,mapping,availability
    def render(self,site,mapping,availability):
        return finalize(site,mapping,'https://templates.moukaeritai.work/',availability_paths=(availability,),coverage_inventory=availability.parent/'inventory.json')
    def test_stale_warning_is_static_accessible_and_links_to_current_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            site,mapping,availability=self.fixture(Path(tmp));self.render(site,mapping,availability)
            source=(site/'ja/policy/cli/index.html').read_text()
            self.assertIn('data-translation-status="stale"',source)
            self.assertIn('role="note" aria-labelledby="translation-stale-title"',source)
            self.assertIn('このページは非正本の参考訳です',source)
            self.assertIn('英語正本が変更されたため',source)
            self.assertIn('古くなっている可能性',source)
            self.assertIn('href="https://templates.moukaeritai.work/policy/cli/" hreflang="en"',source)
            self.assertIn('<link rel="canonical" href="https://templates.moukaeritai.work/policy/cli/">',source)
            self.assertIn('Provider-owned prose',source)
            self.assertLess(source.index('translation-stale-warning'),source.index('Provider-owned prose'))
            canonical=(site/'policy/cli/index.html').read_text()
            self.assertIn('https://templates.moukaeritai.work/ja/policy/cli/',canonical)
            self.assertNotIn('translation-stale-warning',canonical)
    def test_current_status_is_not_recomputed_from_unequal_source_identifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            site,mapping,availability=self.fixture(Path(tmp),'current');self.render(site,mapping,availability)
            source=(site/'ja/policy/cli/index.html').read_text()
            self.assertNotIn('translation-stale-warning',source)
            self.assertIn('日本語参考訳',source)
    def test_missing_translation_does_not_create_route_or_switcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            site,mapping,availability=self.fixture(Path(tmp),'missing');self.render(site,mapping,availability)
            self.assertFalse((site/'ja/policy/cli/index.html').exists())
            self.assertNotIn('translation-switcher',(site/'policy/cli/index.html').read_text())
    def test_malformed_or_incomplete_availability_fails_before_any_html_write(self):
        def mutate(record,field,value):record[field]=value
        for mutation in ('missing','unknown','wrong_owner','wrong_path','duplicate','omitted','unsafe'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                site,mapping,availability=self.fixture(Path(tmp));original={p:p.read_bytes() for p in site.rglob('*.html')}
                data=json.loads(availability.read_text());row=data['records'][0]
                if mutation=='missing':row['status']='missing'
                elif mutation=='unknown':row['status']='synchronized'
                elif mutation=='wrong_owner':row['publication']='composition'
                elif mutation=='wrong_path':row['canonical_destination']='other.md'
                elif mutation=='duplicate':data['records'].append(copy.deepcopy(row))
                elif mutation=='omitted':data['records']=[]
                else:row['canonical_destination']='../escape.md'
                availability.write_text(json.dumps(data))
                with self.assertRaises(TranslationReaderError):self.render(site,mapping,availability)
                self.assertEqual(original,{p:p.read_bytes() for p in site.rglob('*.html')})
    def test_missing_availability_is_not_treated_as_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            site,mapping,_=self.fixture(Path(tmp))
            with self.assertRaises(TranslationReaderError):finalize(site,mapping,'https://templates.moukaeritai.work/')
    def test_canonical_renderer_always_passes_both_authority_owned_models(self):
        source=(ROOT/'site_renderer/render.py').read_text()
        self.assertIn("'--availability',build/'translation-coverage.json'",source)
        self.assertIn("'--availability',build/'site-translation-coverage.json'",source)
        source=(ROOT/'scripts/finalize_translation_reader.py').read_text()
        for forbidden in ('canonical_blob_sha','current_blob_sha','hashlib','translations/manifest.json','git rev-parse'):
            self.assertNotIn(forbidden,source)

    def test_omitted_or_invented_missing_record_is_rejected_before_writes(self):
        for mutation in ('omit', 'extra'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                site,mapping,availability=self.fixture(Path(tmp),'missing')
                before={p:p.read_bytes() for p in site.rglob('*.html')}
                data=json.loads(availability.read_text())
                if mutation=='omit':data['records']=[]
                else:data['records'].append({'publication':'policy','language':'ja','canonical_destination':'policy/undeclared.md','status':'missing'})
                availability.write_text(json.dumps(data))
                with self.assertRaisesRegex(TranslationReaderError,'coverage inventory'):
                    self.render(site,mapping,availability)
                self.assertEqual(before,{p:p.read_bytes() for p in site.rglob('*.html')})
