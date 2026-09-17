"""Final authority boundary regressions, including the canonical transitive path."""
import ast,json,unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
class BoundaryTests(unittest.TestCase):
 def test_retired_provider_authorities_are_absent_from_site(self):
  for path in ('integration','publication-sources.json','publication-staging.json','site-manifest.json','scripts/assemble_publications_v3.py','scripts/produce_publication_bundle.py','scripts/resolve_publication_sources.py'):
   self.assertFalse((ROOT/path).exists(),path)
 def test_no_site_module_imports_an_integration_implementation(self):
  paths=[*ROOT.joinpath('site_renderer').rglob('*.py'),*ROOT.joinpath('scripts').glob('*.py'),*ROOT.joinpath('publication_bundle').rglob('*.py')]
  self.assertTrue(paths)
  for path in paths:
   for node in ast.walk(ast.parse(path.read_text())):
    names=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
    for name in names:self.assertFalse(name=='integration' or name.startswith(('integration.','scripts.assemble_publications','scripts.resolve_publication_sources')),str(path))
 def test_site_producer_has_only_the_locked_bundle_publication_input(self):
  text=(ROOT/'.github/workflows/site-producer.yml').read_text()
  for forbidden in ('composition-source','policy-source','--composition-root','--policy-root','resolve_publication_sources'):
   self.assertNotIn(forbidden,text)
  self.assertIn('acquire_integration_bundle.py',text);self.assertIn('render_publication_bundle.py',text)
 def test_only_site_manual_workflow_can_deploy(self):
  for path in (ROOT/'.github/workflows').glob('*.yml'):
   text=path.read_text()
   if 'pages: write' in text or 'actions/deploy-pages@' in text:
    self.assertEqual(path.name,'deploy-pages.yml');self.assertIn("github.ref == 'refs/heads/site'",text)
    events=yaml.safe_load(text)[True];self.assertEqual(set(events),{'workflow_dispatch'})
 def test_default_branch_provider_event_adapter_delegates_to_exact_integration_controller(self):
  path=ROOT/'.github/workflows/provider-publication-dispatch.yml'
  text=path.read_text()
  self.assertIn('repository_dispatch:',text)
  self.assertIn('publication.provider-qualified',text)
  self.assertIn('integration-reconcile.yml@4ef00ac091d210cb0474da00cf0802836c6c14e3',text)
  for forbidden in ('qualify_integration.py','render_candidate_source_lock.py','publication-sources.json','actions/deploy-pages@'):
   self.assertNotIn(forbidden,text)
 def test_deployment_includes_complete_qualification(self):
  deploy=yaml.safe_load((ROOT/'.github/workflows/deploy-pages.yml').read_text())
  self.assertEqual(set(deploy['jobs']['deploy']['needs']),{'build','artifact_gate','deployment_metadata'})
  self.assertEqual(set(deploy['jobs']['artifact_gate']['needs']),{'deployment_metadata','build'})
  self.assertNotIn('site_ref',deploy['jobs']['build']['with'])
  jobs=yaml.safe_load((ROOT/'.github/workflows/build-pages.yml').read_text())['jobs']
  self.assertIn("github.event_name == 'workflow_dispatch'",jobs['full_qualification']['if'])
  self.assertEqual(yaml.safe_load((ROOT/'.github/workflows/build-pages.yml').read_text())[True]['workflow_call']['outputs']['qualification_gate']['value'],'${{ jobs.full_qualification.result }}')
  self.assertTrue({'check','reference_consumer','cross_authority','core_tests','website_contract','policy','playground','explainability'}<=set(jobs['full_qualification']['needs']))

 def test_manual_chromium_leaf_is_reachable_but_fork_prs_are_rejected(self):
  condition=yaml.safe_load((ROOT/'.github/workflows/site-composition-playground-cross-authority.yml').read_text())['jobs']['producer_consumer']['if']
  cases=[('workflow_dispatch','TakashiSasaki/templates','',True),('pull_request','TakashiSasaki/templates','TakashiSasaki/templates',True),('pull_request','TakashiSasaki/templates','fork/repo',False),('workflow_dispatch','fork/repo','',False),('push','TakashiSasaki/templates','',False)]
  for event,repository,head_repository,expected in cases:
   expression=condition
   for name,value in [('github.event.pull_request.head.repo.full_name',head_repository),('github.repository',repository),('github.event_name',event),('inputs.browser_required','true')]:expression=expression.replace(name,repr(value))
   self.assertEqual(eval(expression.replace('&&',' and ').replace('||',' or '),{'__builtins__':{}}),expected,(event,repository,head_repository))
 def test_routed_preflight_commands_match_current_bundle_only_cli(self):
  import shlex,subprocess,sys
  for path in (ROOT/'.agents/skills/site-pr-exact-head-acceptance/SKILL.md',ROOT/'docs/ci/site-performance.md'):
   text=path.read_text()
   self.assertNotIn('--base ',text);self.assertNotIn('--composition-root',text);self.assertNotIn('--policy-root',text)
   self.assertIn('--bundle <verified Bundle directory>',text)
  help_result=subprocess.run([sys.executable,str(ROOT/'scripts/run_site_preflight.py'),'source-ready','--help'],capture_output=True,text=True)
  self.assertEqual(help_result.returncode,0)
  self.assertIn('artifact-local',subprocess.run([sys.executable,str(ROOT/'scripts/run_site_preflight.py'),'--help'],capture_output=True,text=True).stdout)
  for option in ('--expected-head','--bundle','--site-root'):self.assertIn(option,help_result.stdout)
