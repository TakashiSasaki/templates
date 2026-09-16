"""Immutable transport must fail closed before a renderer sees any content."""
import copy
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile
from ci_artifacts.publication_bundle import pack, extract, binding
from ci_artifacts.transport import ArtifactError
from publication_bundle.contract import BundleError
from tests.test_publication_bundle import fixture, finish, PRODUCER, PROVIDERS


class BundleArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.bundle=fixture(self.root/'bundle');self.manifest=finish(self.bundle)

    def archive(self,malicious=None):
        target=self.root/'bundle.tar';pack(self.bundle,target)
        if malicious:
            with tarfile.open(target,'a') as archive:
                entry=tarfile.TarInfo(malicious)
                if malicious=='symlink':entry.type=tarfile.SYMTYPE;entry.linkname='/etc/passwd'
                archive.addfile(entry,io.BytesIO())
        path=self.root/'bundle.zip'
        with zipfile.ZipFile(path,'w') as z:z.write(target,'bundle.tar')
        return path,'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

    def test_exact_transport_roundtrip(self):
        archive,digest=self.archive()
        result=extract(archive,self.root/'out',archive_digest=digest,identity=self.manifest['identity'],producer=PRODUCER['revision'],providers=PROVIDERS)
        self.assertEqual(result,self.manifest)
        for name in self.manifest['files']:
            self.assertEqual((self.root/'out'/name).read_bytes(),(self.bundle/name).read_bytes())

    def test_corrupt_or_misbound_artifact_has_no_visible_output(self):
        archive,digest=self.archive()
        inputs=dict(archive_digest=digest,identity=self.manifest['identity'],producer=PRODUCER['revision'],providers=PROVIDERS)
        for change in ({'archive_digest':'sha256:'+'0'*64},{'identity':'0'*64},{'producer':'0'*40},{'providers':{**PROVIDERS,'policy':'0'*40}}):
            with self.subTest(change=change),self.assertRaises((ArtifactError,BundleError)):
                extract(archive,self.root/'out',**{**inputs,**change})
            self.assertFalse((self.root/'out').exists())

    def test_unsafe_members_rejected_before_extraction(self):
        for name in ('../outside','/absolute','symlink','bundle.json'):
            with self.subTest(name=name):
                archive,digest=self.archive(name)
                with self.assertRaises(ArtifactError):
                    extract(archive,self.root/'out',archive_digest=digest,identity=self.manifest['identity'],producer=PRODUCER['revision'],providers=PROVIDERS)
                self.assertFalse((self.root/'out').exists())
                (self.root/'bundle.tar').unlink();archive.unlink()

    def test_attempt_window_and_all_identity_bindings(self):
        name='publication-bundle-'+self.manifest['identity']+'-2-site'
        metadata={'id':1,'expired':False,'digest':'sha256:'+'d'*64,'name':name,'workflow_run':{'id':2,'head_sha':'a'*40},'created_at':'2026-09-16T12:00:03Z'}
        run={'id':2,'run_attempt':2,'head_sha':'a'*40,'head_repository':{'full_name':'TakashiSasaki/templates'}}
        job={'name':'build / integration / Qualify Integration candidate (site)','run_attempt':2,'status':'completed','conclusion':'success','started_at':'2026-09-16T12:00:00Z','completed_at':'2026-09-16T12:00:10Z'}
        expected=dict(artifact_id=1,archive_digest=metadata['digest'],run_id=2,attempt=2,producer='a'*40,workflow_head='a'*40,repository='TakashiSasaki/templates',identity=self.manifest['identity'],artifact_name=name)
        binding(metadata,run,[job,{**job,'name':'freshness / Qualify Integration candidate (freshness)'}],**expected)
        for target,key,value in [('metadata','id',3),('metadata','digest','sha256:'+'e'*64),('metadata','expired',True),('metadata','created_at','2026-09-16T11:00:00Z'),('metadata','created_at','not-time'),('metadata','name','other'),('run','run_attempt',1),('run','head_sha','b'*40),('job','run_attempt',1),('job','conclusion','failure'),('job','completed_at','2026-09-16T11:00:00Z')]:
            data=copy.deepcopy({'metadata':metadata,'run':run,'job':job});data[target][key]=value
            with self.subTest(target=target,key=key),self.assertRaises(ArtifactError):binding(data['metadata'],data['run'],[data['job']],**expected)
        with self.assertRaises(ArtifactError):binding(metadata,run,[job,job],**expected)
