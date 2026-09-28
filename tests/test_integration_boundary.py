"""Final authority boundary regressions, including the canonical transitive path."""
import ast,json,unittest
import os
import re
import subprocess
import sys
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
 def test_default_branch_adapter_validates_and_delegates_provider_and_manual_events(self):
  path=ROOT/'.github/workflows/provider-publication-dispatch.yml'
  text=path.read_text()
  workflow=yaml.safe_load(text)
  events=workflow.get('on',workflow.get(True))
  self.assertIn('repository_dispatch',events)
  self.assertIn('publication.provider-qualified',events['repository_dispatch']['types'])
  self.assertIn('workflow_dispatch',events)
  manual=events['workflow_dispatch']['inputs']
  self.assertTrue(manual['producer_ref']['required'])
  self.assertEqual(set(manual),{'producer_ref','composition_ref','policy_ref','modeling_ref'})
  for name in ('composition_ref','policy_ref','modeling_ref'):
   self.assertFalse(manual[name]['required'])
   self.assertEqual(manual[name]['default'],'')

  validation=workflow['jobs']['validate_event']
  self.assertIn("github.ref == 'refs/heads/site'",validation['if'])
  self.assertIn('git/ref/heads/integration',text)
  self.assertIn('integration_ref: ${{ steps.integration.outputs.integration_ref }}',text)
  self.assertIn('set(payload) != expected',text)
  self.assertEqual(validation['outputs']['integration_ref'],'${{ steps.integration.outputs.integration_ref }}')
  self.assertEqual(validation['outputs']['producer_ref'],"${{ github.event_name == 'workflow_dispatch' && steps.manual.outputs.producer_ref || steps.integration.outputs.integration_ref }}")
  self.assertEqual(validation['outputs']['composition_ref'],"${{ github.event_name == 'workflow_dispatch' && steps.manual.outputs.composition_ref || steps.payload.outputs.composition_ref }}")
  self.assertEqual(validation['outputs']['policy_ref'],"${{ github.event_name == 'workflow_dispatch' && steps.manual.outputs.policy_ref || steps.payload.outputs.policy_ref }}")
  self.assertEqual(validation['outputs']['modeling_ref'],"${{ github.event_name == 'workflow_dispatch' && steps.manual.outputs.modeling_ref || steps.payload.outputs.modeling_ref }}")
  self.assertNotIn('client_payload.producer_ref',text)
  self.assertNotIn('client_payload.controller_ref',text)

  caller=workflow['jobs']['integration_controller']
  self.assertEqual(caller['uses'],'TakashiSasaki/templates/.github/workflows/integration-reconcile.yml@ce0f2d2e4f3d6524aa6818e2f38c33850dcbebfb')
  self.assertEqual(caller['with']['producer_ref'],'${{ needs.validate_event.outputs.producer_ref }}')
  self.assertEqual(caller['with']['composition_ref'],'${{ needs.validate_event.outputs.composition_ref || \'\' }}')
  self.assertEqual(caller['with']['policy_ref'],'${{ needs.validate_event.outputs.policy_ref || \'\' }}')
  self.assertEqual(caller['with']['modeling_ref'],'${{ needs.validate_event.outputs.modeling_ref || \'\' }}')
  self.assertEqual(caller['with']['controller_ref'],'${{ needs.validate_event.outputs.controller_ref }}')
  self.assertEqual(caller['secrets'],'inherit')
  self.assertEqual(validation['outputs']['controller_ref'],'${{ steps.controller.outputs.controller_ref }}')
  controller=next(step for step in validation['steps'] if step['id']=='controller')
  self.assertEqual(controller['env']['CONTROLLER_REF'],'${{ vars.PUBLICATION_CONTROLLER_REVISION }}')
  self.assertNotIn('controller_ref',manual)
  self.assertIn('re.fullmatch(r"[0-9a-f]{40}"',text)
  self.assertIn('value and re.fullmatch(r"[0-9a-f]{40}"',text)

  manual_step=next(step for step in validation['steps'] if step.get('id')=='manual')
  match=re.search(r"python3 - <<'PY' >> \"\$GITHUB_OUTPUT\"\n(.*?)\nPY\n",manual_step['run'],re.S)
  self.assertIsNotNone(match)
  validator=match.group(1)
  environment={**os.environ,'PRODUCER_REF':'f'*40,'COMPOSITION_REF':'a'*40,'POLICY_REF':'b'*40,'MODELING_REF':'c'*40}
  valid=subprocess.run([sys.executable,'-c',validator],capture_output=True,text=True,env=environment)
  self.assertEqual(valid.returncode,0,valid.stderr)
  self.assertIn(f'producer_ref={"f"*40}',valid.stdout)
  for field in ('COMPOSITION_REF','POLICY_REF','MODELING_REF'):
   self.assertIn(f'{field.lower()}={environment[field]}',valid.stdout)

  for field in ('COMPOSITION_REF','POLICY_REF','MODELING_REF'):
   environment[field]=''
  valid=subprocess.run([sys.executable,'-c',validator],capture_output=True,text=True,env=environment)
  self.assertEqual(valid.returncode,0,valid.stderr)
  for field in ('COMPOSITION_REF','POLICY_REF','MODELING_REF'):
   self.assertIn(f'{field.lower()}=',valid.stdout)

  self.assertIn('composition_ref=',valid.stdout)
  environment['PRODUCER_REF']='F'*40
  invalid=subprocess.run([sys.executable,'-c',validator],capture_output=True,text=True,env=environment)
  self.assertNotEqual(invalid.returncode,0)
  environment['PRODUCER_REF']='f'*39
  invalid=subprocess.run([sys.executable,'-c',validator],capture_output=True,text=True,env=environment)
  self.assertNotEqual(invalid.returncode,0)
  environment['PRODUCER_REF']='f'*40
  environment['COMPOSITION_REF']='a'*39
  invalid=subprocess.run([sys.executable,'-c',validator],capture_output=True,text=True,env=environment)
  self.assertNotEqual(invalid.returncode,0)

  payload_step=next(step for step in validation['steps'] if step.get('id')=='payload')
  match=re.search(r"python3 - <<'PY' >> \"\$GITHUB_OUTPUT\"\n(.*?)\nPY\n",payload_step['run'],re.S)
  self.assertIsNotNone(match)
  payload_validator=match.group(1)
  provider_workflows={
   'modeling':('Modeling qualification','.github/workflows/modeling-ci.yml'),
   'composition':('Composition Integration compatibility','.github/workflows/reference-consumer-publication.yml'),
   'policy':('Policy Integration compatibility','.github/workflows/integration-compatibility.yml'),
  }
  provider_revision='d'*40
  for provider,(workflow_name,workflow_path) in provider_workflows.items():
   payload={
    'provider':provider,
    'provider_revision':provider_revision,
    'provider_qualification_run_id':'12345',
    'provider_qualification_attempt':'1',
    'qualification_workflow_head':'e'*40,
    'qualification_workflow_name':workflow_name,
    'qualification_workflow_event':'push',
    'qualification_workflow_path':workflow_path,
   }
   valid=subprocess.run(
    [sys.executable,'-c',payload_validator],capture_output=True,text=True,
    env={**os.environ,'PAYLOAD':json.dumps(payload)},
   )
   self.assertEqual(valid.returncode,0,valid.stderr)
   self.assertIn(f'{provider}_ref={provider_revision}',valid.stdout)
  payload['controller_ref']='f'*40
  invalid=subprocess.run(
   [sys.executable,'-c',payload_validator],capture_output=True,text=True,
   env={**os.environ,'PAYLOAD':json.dumps(payload)},
  )
  self.assertNotEqual(invalid.returncode,0)

  for forbidden in ('qualify_integration.py','render_candidate_source_lock.py','publication-sources.json','actions/deploy-pages@'):
   self.assertNotIn(forbidden,text)
  for path in (*ROOT.joinpath('.github/workflows').glob('*.yml'),ROOT/'docs/publication-automation.md'):
   self.assertNotIn('PUBLICATION_APP_TOKEN',path.read_text())

 def test_site_producer_uses_the_current_integration_controller_pin(self):
  text=(ROOT/'.github/workflows/site-producer.yml').read_text()
  self.assertIn(
   'integration-qualification.yml@a92006b95ef67abaa52d59e7a583c1f59656e7a7',
   text,
  )

 def test_site_publication_pr_stops_at_the_independent_review_boundary(self):
  workflow=yaml.safe_load((ROOT/'.github/workflows/publication-reconcile.yml').read_text())
  job=workflow['jobs']['adopt_lock_pr']
  step=next(step for step in job['steps'] if step.get('name')=='Create or reconcile the idempotent Site adoption PR')
  script=step['run']

  self.assertEqual(step['env']['BRANCH'],'automation/site-publication-$IDEMPOTENCY_KEY')
  self.assertIn('gh api --paginate --slurp',script)
  self.assertIn('python3 scripts/verify_site_adoption_pr.py find',script)
  self.assertIn('python3 scripts/verify_site_adoption_pr.py verify-pr',script)
  self.assertIn('refresh_remote_branch()',script)
  self.assertIn('An idempotency branch exists without an open PR; stop for human recovery.',script)
  self.assertIn('gh pr create',script)
  self.assertIn('report_pr_ready "$existing"',script)
  self.assertIn('independent exact-head review',script)
  self.assertIn('separate human merge authorization',script)
  self.assertNotRegex(script,r'(?m)^\s*gh\s+pr\s+merge(?:\s|$)')
  self.assertNotRegex(script,r'(?m)^\s*gh\s+pr\s+review\s+--approve(?:\s|$)')
  self.assertNotRegex(script,r'(?m)^\s*git\s+push\b.*(?:refs/heads/)?site(?:\s|$)')
  pushes=[line.strip() for line in script.splitlines() if line.strip().startswith('git push')]
  self.assertEqual(pushes,['git push --force-with-lease="$remote_ref:" origin "HEAD:$BRANCH"'])
  workflow_text=(ROOT/'.github/workflows/publication-reconcile.yml').read_text()
  self.assertNotIn('actions/deploy-pages@',workflow_text)
  self.assertNotIn('deploy-pages.yml',workflow_text)

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
