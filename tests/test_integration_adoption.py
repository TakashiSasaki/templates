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
   result=identity(repository='TakashiSasaki/templates',site=site_revision,workflow=b'workflow',bundle={k:self.manifest[k] for k in ('schema_version','producer','providers','identity','content_digest')})
   self.assertEqual(result['publication_bundle']['producer']['revision'],self.lock['revision'])
   self.assertNotIn('composition',result);self.assertNotIn('policy',result)
  self.assertEqual(self.lock,before)
 def test_consumer_does_not_reopen_provider_semantics(self):
  self.assertFalse((ROOT/'integration').exists())
  self.assertFalse((ROOT/'publication_bundle/translations.py').exists())
  validate_locked(self.root,self.lock)

 def test_payload_mutation_is_not_hidden_by_provider_metadata(self):
  (self.root/'publication/intro.md').write_text('changed')
  with self.assertRaises(BundleError):validate_locked(self.root,self.lock)
 def test_missing_artifact_evidence_allows_explicit_regeneration(self):
  with patch('site_renderer.acquire.paginated',return_value=[]):self.assertIsNone(locate(self.lock))
 def test_base_receipt_shape_is_verified_before_consumption(self):
  from site_renderer.acquire import verify_receipt
  from unittest.mock import patch
  identity=self.lock['bundle_identity'];digest='sha256:'+'d'*64
  value={'repository':'TakashiSasaki/templates','producer':self.lock['revision'],'identity':identity,
         'run_id':2,'attempt':2,'workflow_head':'a'*40,'artifact_id':1,
         'archive_digest':digest,'artifact_name':f'publication-bundle-{identity}-2-integration'}
  metadata={'id':1,'expired':False,'digest':digest,'name':value['artifact_name'],
            'workflow_run':{'id':2,'head_sha':'a'*40}}
  run={'id':2,'run_attempt':2,'head_sha':'a'*40,
       'head_repository':{'full_name':'TakashiSasaki/templates'},
       'name':'Validate Integration authority','event':'workflow_dispatch',
       'path':'.github/workflows/validate-integration.yml','status':'completed','conclusion':'success'}
  with patch('site_renderer.acquire.api',side_effect=[metadata,run]), \
       patch('site_renderer.acquire.paginated',return_value=[]), \
       patch('site_renderer.acquire.binding') as bound:
   self.assertEqual(verify_receipt(self.lock,value),'repos/TakashiSasaki/templates/actions')
   bound.assert_called_once()
 def test_committed_release_pull_request_event_is_explicitly_supported(self):
  from site_renderer.acquire import verify_receipt
  identity=self.lock['bundle_identity'];digest='sha256:'+'e'*64
  value={'repository':'TakashiSasaki/templates','producer':self.lock['revision'],'identity':identity,
         'run_id':3,'attempt':1,'workflow_head':'b'*40,'artifact_id':2,
         'archive_digest':digest,'artifact_name':f'publication-bundle-{identity}-1-integration'}
  metadata={'id':2,'expired':False,'digest':digest,'name':value['artifact_name'],
            'workflow_run':{'id':3,'head_sha':'b'*40}}
  run={'id':3,'run_attempt':1,'head_sha':'b'*40,
       'head_repository':{'full_name':'TakashiSasaki/templates'},
       'name':'Validate Integration authority','event':'pull_request',
       'path':'.github/workflows/validate-integration.yml','status':'completed','conclusion':'success'}
  with patch('site_renderer.acquire.api',side_effect=[metadata,run]), \
       patch('site_renderer.acquire.paginated',return_value=[]), \
       patch('site_renderer.acquire.binding') as bound:
   self.assertEqual(verify_receipt(self.lock,value),'repos/TakashiSasaki/templates/actions')
   bound.assert_called_once()
 def test_unapproved_workflow_identity_is_rejected(self):
  from ci_artifacts.transport import ArtifactError
  from site_renderer.acquire import verify_receipt
  identity=self.lock['bundle_identity'];digest='sha256:'+'f'*64
  value={'repository':'TakashiSasaki/templates','producer':self.lock['revision'],'identity':identity,
         'run_id':4,'attempt':1,'workflow_head':'c'*40,'artifact_id':3,
         'archive_digest':digest,'artifact_name':f'publication-bundle-{identity}-1-integration'}
  metadata={'id':3,'expired':False,'digest':digest,'name':value['artifact_name'],
            'workflow_run':{'id':4,'head_sha':'c'*40}}
  run={'id':4,'run_attempt':1,'head_sha':'c'*40,
       'head_repository':{'full_name':'TakashiSasaki/templates'},
       'name':'Untrusted workflow','event':'workflow_dispatch',
       'path':'.github/workflows/validate-integration.yml','status':'completed','conclusion':'success'}
  with patch('site_renderer.acquire.api',side_effect=[metadata,run]), \
       patch('site_renderer.acquire.paginated',return_value=[]):
   with self.assertRaisesRegex(ArtifactError,'unapproved workflow identity'):
    verify_receipt(self.lock,value)
 def test_active_site_adoption_caller_may_consume_completed_nested_job(self):
  from ci_artifacts.transport import ArtifactError
  from site_renderer.acquire import verify_receipt
  identity=self.lock['bundle_identity'];digest='sha256:'+'a'*64
  value={'repository':'TakashiSasaki/templates','producer':self.lock['revision'],'identity':identity,
         'run_id':5,'attempt':1,'workflow_head':'d'*40,'artifact_id':4,
         'archive_digest':digest,'artifact_name':f'publication-bundle-{identity}-1-site-adoption'}
  metadata={'id':4,'expired':False,'digest':digest,'name':value['artifact_name'],
            'workflow_run':{'id':5,'head_sha':'d'*40},'created_at':'2026-09-16T12:00:03Z'}
  run={'id':5,'run_attempt':1,'head_sha':'d'*40,
       'head_repository':{'full_name':'TakashiSasaki/templates'},
       'name':'Build documentation artifact','event':'pull_request',
       'path':'.github/workflows/build-pages.yml','status':'in_progress','conclusion':None,
       'started_at':'2026-09-16T12:00:00Z'}
  job={'name':'build / regenerate / Qualify Integration candidate (site-adoption)',
       'run_attempt':1,'status':'completed','conclusion':'success',
       'started_at':'2026-09-16T12:00:00Z','completed_at':'2026-09-16T12:00:10Z'}
  with patch('site_renderer.acquire.api',side_effect=[metadata,run]), \
       patch('site_renderer.acquire.paginated',return_value=[job]), \
       patch.dict('os.environ',{'GITHUB_ACTIONS':'true','GITHUB_RUN_ID':'5'},clear=False):
   self.assertEqual(verify_receipt(self.lock,value),'repos/TakashiSasaki/templates/actions')
 def test_active_site_adoption_caller_may_consume_when_github_reports_parent_queued(self):
  from site_renderer.acquire import verify_receipt
  identity=self.lock['bundle_identity'];digest='sha256:'+'c'*64
  value={'repository':'TakashiSasaki/templates','producer':self.lock['revision'],'identity':identity,
         'run_id':8,'attempt':1,'workflow_head':'f'*40,'artifact_id':6,
         'archive_digest':digest,'artifact_name':f'publication-bundle-{identity}-1-site-adoption'}
  metadata={'id':6,'expired':False,'digest':digest,'name':value['artifact_name'],
            'workflow_run':{'id':8,'head_sha':'f'*40},'created_at':'2026-09-16T12:00:03Z'}
  run={'id':8,'run_attempt':1,'head_sha':'f'*40,
       'head_repository':{'full_name':'TakashiSasaki/templates'},
       'name':'Build documentation artifact','event':'pull_request',
       'path':'.github/workflows/build-pages.yml','status':'queued','conclusion':None,
       'started_at':'2026-09-16T12:00:00Z'}
  job={'name':'build / regenerate / Qualify Integration candidate (site-adoption)',
       'run_attempt':1,'status':'completed','conclusion':'success',
       'started_at':'2026-09-16T12:00:00Z','completed_at':'2026-09-16T12:00:10Z'}
  with patch('site_renderer.acquire.api',side_effect=[metadata,run]), \
       patch('site_renderer.acquire.paginated',return_value=[job]), \
       patch.dict('os.environ',{'GITHUB_ACTIONS':'true','GITHUB_RUN_ID':'8'},clear=False):
   self.assertEqual(verify_receipt(self.lock,value),'repos/TakashiSasaki/templates/actions')
 def test_active_site_adoption_caller_requires_the_current_actions_run(self):
  from ci_artifacts.transport import ArtifactError
  from site_renderer.acquire import verify_receipt
  identity=self.lock['bundle_identity'];digest='sha256:'+'b'*64
  value={'repository':'TakashiSasaki/templates','producer':self.lock['revision'],'identity':identity,
         'run_id':6,'attempt':1,'workflow_head':'e'*40,'artifact_id':5,
         'archive_digest':digest,'artifact_name':f'publication-bundle-{identity}-1-site-adoption'}
  metadata={'id':5,'expired':False,'digest':digest,'name':value['artifact_name'],
            'workflow_run':{'id':6,'head_sha':'e'*40},'created_at':'2026-09-16T12:00:03Z'}
  run={'id':6,'run_attempt':1,'head_sha':'e'*40,
       'head_repository':{'full_name':'TakashiSasaki/templates'},
       'name':'Build documentation artifact','event':'pull_request',
       'path':'.github/workflows/build-pages.yml','status':'in_progress','conclusion':None,
       'started_at':'2026-09-16T12:00:00Z'}
  job={'name':'build / regenerate / Qualify Integration candidate (site-adoption)',
       'run_attempt':1,'status':'completed','conclusion':'success',
       'started_at':'2026-09-16T12:00:00Z','completed_at':'2026-09-16T12:00:10Z'}
  with patch('site_renderer.acquire.api',side_effect=[metadata,run]), \
       patch('site_renderer.acquire.paginated',return_value=[job]), \
       patch.dict('os.environ',{'GITHUB_ACTIONS':'true','GITHUB_RUN_ID':'7'},clear=False):
   with self.assertRaisesRegex(ArtifactError,'workflow run was not successful'):
    verify_receipt(self.lock,value)
 def test_trusted_deployment_lane_never_falls_back_to_regeneration(self):
  with patch('site_renderer.acquire.paginated',return_value=[]):self.assertIsNone(locate(self.lock,require_trusted_release=True))
 def test_misbound_artifact_evidence_cannot_fall_back_to_regeneration(self):
  from ci_artifacts.transport import ArtifactError
  with patch('site_renderer.acquire.paginated',return_value=[{'id':1,'head_sha':'f'*40,'conclusion':'success'}]),self.assertRaises(ArtifactError):locate(self.lock)
 def test_discovery_is_a_bundle_projection_of_four_authorities(self):
  template=read_json(ROOT/'agent.json');schema=read_json(ROOT/'schemas/agent-bootstrap.schema.json')
  jsonschema.validate(template,schema);result=project(template,self.manifest);jsonschema.validate(result,schema)
  self.assertEqual(result['integration_source']['identity'],self.manifest['identity'])
  for name,revision in self.manifest['providers'].items():self.assertEqual(result['authorities'][name]['publication_revision'],revision)
  self.assertEqual(result['authorities']['site']['role'],'presentation-runtime-deployment')
  self.assertTrue(all(v['owner']=='integration' for v in result['integration_contracts'].values()))
