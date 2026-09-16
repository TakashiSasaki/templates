"""The Site selection and consumer boundary are independent of provider implementation."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import jsonschema
from publication_bundle.contract import BundleError,canonical,read_json
from site_renderer.bundle import load_lock,validate_locked
from site_renderer.discovery import project
from site_renderer.acquire import locate
from tests.bundle_consumer_fixture import fixture,finish,lock
ROOT=Path(__file__).resolve().parents[1]

class AdoptionTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=fixture(Path(tmp.name)/'bundle');self.manifest=finish(self.root);self.lock=lock(self.manifest)
 def test_only_exact_integration_release_and_contract_can_be_selected(self):
  for key,value in [('revision','integration'),('revision','a'*7),('bundle_schema',1),('schema_version',True),('bundle_identity',''),('content_digest','bad')]:
   with self.subTest(key=key):
    p=self.root.parent/'lock.json';p.write_bytes(canonical({**self.lock,key:value}))
    with self.assertRaises(BundleError):load_lock(p)
  for key,value in [('composition','b'*40),('policy','c'*40)]:
   p=self.root.parent/'lock.json';p.write_bytes(canonical({**self.lock,key:value}))
   with self.assertRaises(BundleError):load_lock(p)
 def test_lock_binds_revision_schema_identity_and_content(self):
  validate_locked(self.root,self.lock)
  for key,value in [('revision','f'*40),('bundle_schema',1),('bundle_identity','e'*64),('content_digest','e'*64)]:
   with self.subTest(key=key),self.assertRaises(BundleError):validate_locked(self.root,{**self.lock,key:value})
 def test_site_changes_do_not_advance_integration_selection(self):
  before=copy.deepcopy(self.lock)
  for site_revision in ('e'*40,'f'*40):
   from scripts.site_build_artifact import identity
   result=identity(repository='TakashiSasaki/templates',site=site_revision,composition='a'*40,policy='a'*40,workflow=b'workflow',bundle={k:self.manifest[k] for k in ('schema_version','producer','providers','identity','content_digest')})
   self.assertEqual(result['publication_bundle']['producer']['revision'],self.lock['revision'])
   self.assertNotIn('composition',result);self.assertNotIn('policy',result)
  self.assertEqual(self.lock,before)
 def test_consumer_does_not_reopen_provider_semantics(self):
  with patch('publication_bundle.source_models.validate_sources',side_effect=AssertionError('provider source semantics')),patch('publication_bundle.translations.validate_translations',side_effect=AssertionError('provider translation semantics')):
   validate_locked(self.root,self.lock)
 def test_payload_mutation_is_not_hidden_by_provider_metadata(self):
  (self.root/'publication/intro.md').write_text('changed')
  with self.assertRaises(BundleError):validate_locked(self.root,self.lock)
 def test_missing_artifact_evidence_allows_explicit_regeneration(self):
  with patch('site_renderer.acquire.paginated',return_value=[]):self.assertIsNone(locate(self.lock))
 def test_misbound_artifact_evidence_cannot_fall_back_to_regeneration(self):
  from ci_artifacts.transport import ArtifactError
  with patch('site_renderer.acquire.paginated',return_value=[{'id':1,'head_sha':'f'*40,'conclusion':'success'}]),self.assertRaises(ArtifactError):locate(self.lock)
 def test_discovery_is_a_bundle_projection_of_four_authorities(self):
  template=read_json(ROOT/'agent.json');schema=read_json(ROOT/'assets/schemas/agent-bootstrap.schema.json')
  jsonschema.validate(template,schema);result=project(template,self.manifest);jsonschema.validate(result,schema)
  self.assertEqual(result['integration_source']['identity'],self.manifest['identity'])
  for name,revision in self.manifest['providers'].items():self.assertEqual(result['authorities'][name]['publication_revision'],revision)
  self.assertEqual(result['authorities']['site']['role'],'presentation-runtime-deployment')
  self.assertTrue(all(v['owner']=='integration' for v in result['integration_contracts'].values()))
