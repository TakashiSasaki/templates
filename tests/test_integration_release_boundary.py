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
                         ['integration-source','controller-source','composition-source','policy-source','modeling-source'])
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

    def test_static_compatibility_preflight_gates_heavy_bundle_qualification(self):
        workflow = (ROOT / '.github/workflows/integration-qualification.yml').read_text()
        self.assertIn('qualify_compatibility_preflight.py', workflow)
        self.assertIn('preflight_report="$RUNNER_TEMP/integration-preflight-report.json"', workflow)
        self.assertIn('integration-preflight-${{ github.run_attempt }}', workflow)
        preflight = workflow.index('qualify_compatibility_preflight.py')
        qualification = workflow.index('qualify_integration.py')
        self.assertLess(preflight, qualification)
        self.assertIn(
            "steps.preflight.outputs.classification != 'COMPATIBLE_PENDING_QUALIFICATION'",
            workflow,
        )
        self.assertIn('Create isolated provider materialization checkouts', workflow)
        self.assertNotIn('continue-on-error: true', workflow)

    def test_reconciliation_requires_trusted_bundle_receipt_and_does_not_execute_candidate_code(self):
        reconcile = (ROOT / '.github/workflows/integration-reconcile.yml').read_text()
        self.assertIn('publication_bundle_artifact.py "${args[@]}"', reconcile)
        self.assertIn('verify_qualification_report.py', reconcile)
        self.assertIn('--qualification qualification/verified-report.json', reconcile)
        self.assertIn('--source-qualification qualification/compatibility-report.json', reconcile)
        controller = reconcile.split('  controller:', 1)[1].split('  promote_lock_pr:', 1)[0]
        self.assertNotIn('integration-source/scripts/', controller)
        self.assertNotIn('candidate-root', controller)
        qualification = (ROOT / '.github/workflows/integration-qualification.yml').read_text()
        self.assertIn('verify_bundle_equivalence.py', qualification)
        self.assertIn('trusted_rebuild: true', reconcile)
        self.assertIn('--code-revision "$CONTROLLER"', qualification)
        self.assertNotIn('test "$PRODUCER" = "$CONTROLLER"', qualification)
        self.assertIn('PUBLICATION_CONTROLLER_REVISION', reconcile)
        self.assertIn('EXPECTED_CONSUMER_BASE: ${{ steps.base.outputs.revision }}', reconcile)
        self.assertIn('--workflow-path "$WORKFLOW_PATH"', reconcile)

    def test_privileged_promotion_uses_only_the_active_controller_pin(self):
        reconcile = (ROOT / '.github/workflows/integration-reconcile.yml').read_text()
        promotion = reconcile.split('  promote_lock_pr:', 1)[1]
        self.assertIn('CONTROLLER_REF: ${{ vars.PUBLICATION_CONTROLLER_REVISION }}', promotion)
        self.assertIn('ref: ${{ vars.PUBLICATION_CONTROLLER_REVISION }}', promotion)
        self.assertIn('Bind privileged controller checkout to the active pin', promotion)
        self.assertNotIn('inputs.controller_ref', promotion)
        controller = reconcile.split('  controller:', 1)[1].split('  promote_lock_pr:', 1)[0]
        self.assertIn('vars.PUBLICATION_CONTROLLER_REVISION || inputs.controller_ref || github.sha', controller)
        self.assertIn('Bind the reconciliation controller to its trusted identity', controller)

    def test_privileged_promotion_revalidates_live_target_and_pr_binding_before_mutation(self):
        reconcile = (ROOT / '.github/workflows/integration-reconcile.yml').read_text()
        promotion = reconcile.split('  promote_lock_pr:', 1)[1]
        self.assertIn('git -C integration-base fetch --quiet origin refs/heads/integration', promotion)
        self.assertIn('publication_promotion_intent.py verify-target', promotion)
        self.assertIn('publication_promotion_intent.py "${args[@]}"', promotion)
        self.assertIn('refs/heads/$BRANCH:refs/remotes/origin/$BRANCH', promotion)
        self.assertIn('git -C integration-base push --force-with-lease="refs/heads/$BRANCH:$branch_before"', promotion)
        self.assertIn('verify_target\n          git -C integration-base push', promotion)
        self.assertIn('verify_target\n            gh pr create', promotion)
        self.assertIn('verify_existing "$existing"\n          gh pr merge', promotion)
        self.assertGreaterEqual(promotion.count('verify_existing "$existing"'), 4)
        self.assertNotIn('remains authoritative', promotion)

    def test_promotion_receipt_keeps_trusted_activation_gate_at_notify_boundary(self):
        workflow = (ROOT / '.github/workflows/integration-promotion-notify.yml').read_text()
        notify = workflow.split('  notify:', 1)[1]
        for required in (
            "vars.PUBLICATION_AUTOMATION_MODE == 'adoption-only'",
            "vars.PUBLICATION_AUTOMATION_AUTHORIZED == 'true'",
            "vars.PUBLICATION_POLICY_REVISION != ''",
            "vars.PUBLICATION_CONTROLLER_REVISION != ''",
            "vars.PUBLICATION_AUTOMATION_KILL_SWITCH != 'true'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, notify)
        self.assertIn('--workflow-path "$WORKFLOW_PATH"', workflow)
        self.assertNotIn('--intent producer-source/publication-promotion-intent.json', workflow)

    def test_post_merge_automation_pr_provenance_gates_the_trusted_chain(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/integration-promotion-notify.yml').read_text())
        jobs = workflow['jobs']
        validation = jobs['validate_promotion_intent']
        commands = '\n'.join(step.get('run', '') for step in validation['steps'])
        self.assertIn('publication_promotion_intent.py verify-merged-pr', commands)
        self.assertIn('--event "$GITHUB_EVENT_PATH"', commands)
        self.assertIn('--repository "$GITHUB_REPOSITORY"', commands)

        def dependencies(job):
            needed = jobs[job].get('needs', [])
            return [needed] if isinstance(needed, str) else needed

        for job in ('release_qualification', 'verify_release', 'notify'):
            with self.subTest(job=job):
                self.assertIn('validate_promotion_intent', dependencies(job))
                self.assertIn(
                    "needs.validate_promotion_intent.result == 'success'",
                    jobs[job]['if'],
                )

    def test_existing_selection_has_a_trusted_promotion_intent_path(self):
        reconcile = yaml.safe_load((ROOT / '.github/workflows/integration-reconcile.yml').read_text())
        controller_steps = reconcile['jobs']['controller']['steps']
        promote_steps = reconcile['jobs']['promote_lock_pr']['steps']
        controller_commands = '\n'.join(step.get('run', '') for step in controller_steps)
        promote_commands = '\n'.join(step.get('run', '') for step in promote_steps)
        self.assertIn('publication_promotion_intent.py build', controller_commands)
        self.assertIn('publication-promotion-intent-${{ needs.qualify.outputs.bundle_identity }}', '\n'.join(str(step.get('with', {})) for step in controller_steps))
        self.assertIn('actions/download-artifact@', '\n'.join(step.get('uses', '') for step in promote_steps))
        self.assertIn('publication_promotion_intent.py verify', promote_commands)
        self.assertIn('publication-promotion-intent.json', promote_commands)
        self.assertIn("needs.controller.outputs.classification == 'AUTO_PROCESSABLE'", reconcile['jobs']['promote_lock_pr']['if'])

        notify = yaml.safe_load((ROOT / '.github/workflows/integration-promotion-notify.yml').read_text())
        self.assertIn('validate_promotion_intent', notify['jobs'])
        self.assertIn('verify-merged', '\n'.join(step.get('run', '') for step in notify['jobs']['validate_promotion_intent']['steps']))
        self.assertIn('needs.validate_promotion_intent.result == \'success\'', notify['jobs']['release_qualification']['if'])

    def test_bundle_receipt_uses_github_workflow_path_shape(self):
        for name, expected_count in (
            ('integration-reconcile.yml', 2),
            ('integration-promotion-notify.yml', 1),
        ):
            workflow = (ROOT / '.github/workflows' / name).read_text()
            with self.subTest(workflow=name):
                self.assertEqual(
                    workflow.count(
                        'WORKFLOW_PATH=".github/workflows/${GITHUB_WORKFLOW_REF#*/.github/workflows/}"'
                    ),
                    expected_count,
                )
                self.assertEqual(
                    workflow.count('WORKFLOW_PATH="${GITHUB_WORKFLOW_REF#*/.github/workflows/}"'),
                    0,
                )

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
