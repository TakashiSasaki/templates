"""Site alone maps semantic documents into the two audience surfaces."""
import json
from pathlib import Path
import tempfile
import unittest
from publication_bundle.contract import canonical, inventory, digest
from site_renderer.bundle import validate
from site_renderer.surfaces import project, copy_publication
from tests.bundle_consumer_fixture import fixture, PRODUCER

ROOT=Path(__file__).resolve().parents[1]


class SurfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.bundle=fixture(self.base/'bundle')
        for name in ('navigation.json','reader-navigation-runtime.json'):(self.bundle/name).unlink()
        providers={'additional':'e'*40}
        def write(name,value):(self.bundle/name).write_bytes(canonical(value))
        write('provenance.json',{'schema_version':1,'producer':PRODUCER,'providers':providers})
        write('guided-navigation.json',{'schema_version':2,'repository':'TakashiSasaki/templates','providers':[]})
        write('guided-locales.json',{'schema_version':1,'canonical_graph_schema_version':2,'canonical_language':'en','locales':[]})
        write('documents.json',[{'publication':'additional','document':'intro','source':'README.md',
                               'destination':'intro.md','title':'Additional','slot':False}])
        files=inventory(self.bundle)
        manifest=dict(schema_version=5,producer=PRODUCER,providers=providers,
                      configuration_digest='d'*64,files=files,content_digest=digest(canonical(files)))
        manifest['identity']=digest(canonical(manifest));write('bundle.json',manifest)
        self.manifest=validate(self.bundle)

    def test_unknown_provider_is_visible_without_editing_site_configuration(self):
        docs,nav,relocations,_,_=project(ROOT,self.bundle)
        self.assertEqual(relocations['intro.md'],'use/intro.md')
        self.assertEqual(nav['audience_runtime']['overviews'],{'use':'/use/','maintain':'/maintain/'})
        self.assertTrue(any(d['publication']=='additional' for d in docs))
        self.assertEqual({d['destination'] for d in docs if d['document'] in {'use-home','maintain-home'}},
                         {'use/index.md','maintain/index.md'})
        output=self.base/'docs';output.mkdir()
        copy_publication(self.bundle,output,self.manifest,relocations)
        self.assertTrue((output/'use/intro.md').is_file())
        # Projection reads the Bundle; it does not add presentation files to it.
        self.assertEqual(validate(self.bundle)['identity'],self.manifest['identity'])

    def test_maintainer_classification_can_change_with_only_site_configuration(self):
        import shutil
        source=self.base/'site';source.mkdir()
        shutil.copytree(ROOT/'docs',source/'docs')
        for p in json.loads((ROOT/'docs/publication-catalog.json').read_text())['documents']:
            path=source/p['source']
            if not path.exists():path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p['source'],path)
        settings=json.loads((ROOT/'surfaces.json').read_text());settings['maintainer_documents']['additional']=['intro']
        (source/'surfaces.json').write_text(json.dumps(settings))
        _,_,routes,_,_=project(source,self.bundle)
        self.assertEqual(routes['intro.md'],'maintain/intro.md')
        self.assertEqual(validate(self.bundle)['identity'],self.manifest['identity'])

    def test_transport_acquires_complete_payload_and_rejects_corrupt_archive(self):
        import io
        import tarfile
        import zipfile
        from unittest.mock import patch
        from site_renderer import channel
        from publication_bundle.contract import BundleError
        tar_bytes=io.BytesIO()
        with tarfile.open(fileobj=tar_bytes,mode='w') as tar:
            tar.add(self.bundle,arcname='.')
        zipped=io.BytesIO()
        with zipfile.ZipFile(zipped,'w') as archive:
            archive.writestr('publication.tar',tar_bytes.getvalue())
        payload=zipped.getvalue()
        run={'id':1,'path':'.github/workflows/integration-publish.yml','head_branch':'integration',
             'event':'push','head_repository':{'full_name':channel.REPOSITORY},'status':'completed',
             'conclusion':'success','run_attempt':1,'head_sha':PRODUCER['revision']}
        artifact={'id':2,'digest':'sha256:'+digest(payload)}
        for corrupt in (False,True):
            output=self.base/('corrupt' if corrupt else 'acquired')
            def download(args,**kwargs):
                kwargs['stdout'].write(payload + b'corruption' if corrupt else payload)
            with patch.object(channel,'select',return_value=(run,artifact)), \
                 patch.object(channel,'api',return_value=run), \
                 patch.object(channel.subprocess,'run',side_effect=download):
                if corrupt:
                    with self.assertRaises(ValueError):channel.acquire(output)
                    self.assertFalse(output.exists())
                else:
                    result=channel.acquire(output)
                    self.assertEqual(result['bundle_identity'],self.manifest['identity'])
                    self.assertEqual(validate(output)['identity'],self.manifest['identity'])
