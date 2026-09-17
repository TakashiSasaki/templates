from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml
from integration.freshness import classify,PublicationFreshnessError

ROOT=Path(__file__).resolve().parents[1]

class ReleaseBoundaryTests(unittest.TestCase):
    def test_active_workflows_use_runner_python_without_runtime_selection(self):
        for workflow in sorted((ROOT / ".github/workflows").glob("*.yml")):
            text = workflow.read_text(encoding="utf-8")
            with self.subTest(workflow=workflow.name):
                self.assertNotIn("actions/setup-python", text)
                self.assertNotIn("python-version", text)
                self.assertNotIn("windows-", text.lower())

    def test_stacked_authority_base_is_not_filtered_by_branch_spelling(self):
        text = (ROOT / ".github/workflows/validate-integration.yml").read_text()
        pull_request = text.split("  pull_request:\n", 1)[1].split(
            "  push:\n", 1
        )[0]
        self.assertNotIn("branches:", pull_request)
        self.assertNotIn("integration-feature-with-an-arbitrary-name", pull_request)

    def test_workflow_reaches_qualification_without_site_or_write_permissions(self):
        caller=yaml.safe_load((ROOT/'.github/workflows/validate-integration.yml').read_text())
        workflow=yaml.safe_load((ROOT/'.github/workflows/integration-qualification.yml').read_text())
        self.assertEqual(caller['jobs']['qualification']['uses'],'./.github/workflows/integration-qualification.yml')
        self.assertEqual(caller['jobs']['qualification']['if'],'${{ github.event_name == \'workflow_dispatch\' }}')
        self.assertEqual(caller['jobs']['qualification']['with']['producer_ref'],'${{ inputs.producer_ref }}')
        self.assertEqual(caller['jobs']['qualification']['with']['composition_ref'],'${{ inputs.composition_ref }}')
        self.assertEqual(caller['jobs']['qualification']['with']['policy_ref'],'${{ inputs.policy_ref }}')
        self.assertEqual(caller['jobs']['qualification']['needs'],'contracts')
        for value in (caller,workflow):self.assertTrue(all(p=='read' for p in value['permissions'].values()))
        steps=workflow['jobs']['qualify']['steps']
        self.assertEqual([s['with']['path'] for s in steps if s.get('uses','').startswith('actions/checkout@')],
                         ['integration-source','composition-source','policy-source','modeling-source'])
        modeling_checkout = next(
            step for step in steps if step.get('with', {}).get('path') == 'modeling-source'
        )
        self.assertIn('steps.refs.outputs.modeling', modeling_checkout['if'])
        integration_checkout = next(
            step for step in steps if step.get('with', {}).get('path') == 'integration-source'
        )
        self.assertEqual(integration_checkout['with']['fetch-depth'], 0)
        commands='\n'.join(s.get('run','') for s in steps)
        for required in ('qualify_integration.py','run_integration_preflight.py fast','publication_bundle_artifact.py pack','--expected "$EXPECTED_PRODUCER"'):self.assertIn(required,commands)
        for obsolete in ('test_bundle_review_invariants','test_translation_manifest_closure','verify_bootstrap_equivalence.py','bootstrap_equivalence'):self.assertNotIn(obsolete,commands)
        for prohibited in ('site_renderer','render_publication_bundle','playwright','deploy-pages','upload-pages-artifact','pages: write','site-source'):
            self.assertNotIn(prohibited,(ROOT/'.github/workflows/integration-qualification.yml').read_text())

    def test_exact_producer_binding_rejects_mutable_and_mismatched_inputs(self):
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        with tempfile.TemporaryDirectory() as tmp:
            for expected in (head,'integration','0'*40):
                output=Path(tmp)/('out-'+expected)
                result=subprocess.run([sys.executable,'scripts/resolve_producer_checkout.py','--root',str(ROOT),'--expected',expected,'--output',str(output)],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(result.returncode==0,expected==head,result.stderr)
                if expected!=head:self.assertFalse(output.exists())

    def test_freshness_is_read_only_exact_identity_relation(self):
        self.assertEqual(classify('a'*40,'a'*40),'current')
        self.assertEqual(classify('a'*40,'b'*40),'different')
        for bad in ('composition','policy','a'*39,'A'*40):
            with self.assertRaises(PublicationFreshnessError):classify('a'*40,bad)
