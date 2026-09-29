import ast
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
import yaml
from integration.freshness import classify,PublicationFreshnessError

ROOT=Path(__file__).resolve().parents[1]


_ACTIONS_EXPRESSION_TOKEN = re.compile(
    r"(?P<string>'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")"
    r"|(?P<operator>&&|\|\|)"
    r"|(?P<boolean>\btrue\b|\bfalse\b)",
    re.IGNORECASE,
)


def validate_actions_if_expression(condition):
    """Parse the complete expression subset used by these promotion job gates."""
    expression = condition.strip()
    if expression.startswith('${{') and expression.endswith('}}'):
        expression = expression[3:-2].strip()

    def translate(match):
        token = match.group(0)
        if match.lastgroup == 'operator':
            return ' and ' if token == '&&' else ' or '
        if match.lastgroup == 'boolean':
            return 'True' if token.lower() == 'true' else 'False'
        return token

    ast.parse(_ACTIONS_EXPRESSION_TOKEN.sub(translate, expression), mode='eval')


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
        self.assertEqual(
            workflow['jobs']['qualify']['outputs']['workflow_head'],
            '${{ github.event.pull_request.head.sha || github.sha }}',
        )
        validate_actions_if_expression(workflow['jobs']['qualify']['outputs']['workflow_head'])
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
        self.assertRegex(
            promotion,
            r'verify_existing "\$existing"\s+verify_existing "\$existing"\s+report_pr_ready "\$existing"',
        )
        self.assertGreaterEqual(promotion.count('verify_existing "$existing"'), 4)
        self.assertNotIn('remains authoritative', promotion)

    def test_publication_promotion_stops_at_the_independent_review_boundary(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/integration-reconcile.yml').read_text())
        job = workflow['jobs']['promote_lock_pr']
        step = next(step for step in job['steps'] if step.get('name') == 'Revalidate the live target before every privileged PR action')
        script = step['run']

        self.assertEqual(
            step['env']['BRANCH'],
            'automation/publication-${{ needs.controller.outputs.idempotency_key }}',
        )
        self.assertIn('gh pr create --repo "$GITHUB_REPOSITORY" --base integration --head "$BRANCH"', script)
        self.assertIn('open_pr_numbers()', script)
        self.assertIn('verify_existing "$existing"', script)
        self.assertIn('report_pr_ready "$existing"', script)
        self.assertIn('independent exact-head review', script)
        self.assertIn('separate human merge authorization', script)
        self.assertNotRegex(script, r'(?m)^\s*gh\s+pr\s+merge(?:\s|$)')
        self.assertNotRegex(script, r'(?m)^\s*git(?:\s+-C integration-base)?\s+push\b.*(?:refs/heads/)?integration(?:\s|$)')

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

    def test_read_only_promotion_checks_run_fail_closed_before_notify(self):
        workflow = yaml.safe_load(
            (ROOT / '.github/workflows/integration-promotion-notify.yml').read_text()
        )
        jobs = workflow['jobs']
        read_only_jobs = (
            'validate_promotion_intent',
            'release_qualification',
            'verify_release',
        )
        for name in read_only_jobs:
            with self.subTest(job=name):
                condition = jobs[name]['if']
                self.assertNotIn("vars.PUBLICATION_AUTOMATION_AUTHORIZED == 'true'", condition)
                self.assertNotIn("vars.PUBLICATION_AUTOMATION_KILL_SWITCH != 'true'", condition)
                permissions = jobs[name].get('permissions', {})
                self.assertTrue(permissions)
                self.assertTrue(all(value == 'read' for value in permissions.values()))

        notify = jobs['notify']['if']
        self.assertIn("vars.PUBLICATION_AUTOMATION_AUTHORIZED == 'true'", notify)
        self.assertIn("vars.PUBLICATION_AUTOMATION_KILL_SWITCH != 'true'", notify)

    def test_promoted_qualification_report_download_flattens_one_exact_artifact(self):
        workflow = yaml.safe_load(
            (ROOT / '.github/workflows/integration-promotion-notify.yml').read_text()
        )
        verify_steps = workflow['jobs']['verify_release']['steps']
        download = next(
            step for step in verify_steps
            if step.get('name') == 'Download the exact candidate qualification report'
        )
        self.assertRegex(download['uses'], r'^actions/download-artifact@[^\s]+$')
        self.assertEqual(
            download['with'],
            {
                'artifact-ids': '${{ needs.release_qualification.outputs.qualification_artifact_id }}',
                'path': 'qualification',
                'merge-multiple': True,
            },
        )

        verify = next(
            step for step in verify_steps
            if step.get('name') == 'Consume and independently verify the exact promoted Bundle'
        )
        verify_args = verify['run'].split('verify_args=(', 1)[1].split(')', 1)[0]
        report_args = [
            line.strip() for line in verify_args.splitlines()
            if line.strip().startswith('--report ')
        ]
        self.assertEqual(report_args, ['--report qualification/compatibility-report.json'])
        for heuristic in ('find qualification', 'glob(', 'rglob(', '*.json', '**/*.json'):
            with self.subTest(heuristic=heuristic):
                self.assertNotIn(heuristic, verify['run'])

        archive_bytes = BytesIO()
        with zipfile.ZipFile(archive_bytes, 'w') as archive:
            archive.writestr('compatibility-report.json', '{"result":"qualified"}\n')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'qualification'
            target.mkdir()
            with zipfile.ZipFile(BytesIO(archive_bytes.getvalue())) as archive:
                self.assertEqual(archive.namelist(), ['compatibility-report.json'])
                archive.extractall(target)
            self.assertTrue((target / 'compatibility-report.json').is_file())

    def test_notify_builds_a_versioned_three_property_site_envelope(self):
        workflow = yaml.safe_load(
            (ROOT / '.github/workflows/integration-promotion-notify.yml').read_text()
        )
        notify_steps = workflow['jobs']['notify']['steps']
        checkout = next(
            step for step in notify_steps
            if step.get('name') == 'Check out the exact merged Integration dispatch helper'
        )
        self.assertEqual(
            checkout['uses'],
            'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1',
        )
        self.assertEqual(
            checkout['with'],
            {
                'ref': '${{ needs.release_qualification.outputs.producer_revision }}',
                'path': 'producer-source',
                'fetch-depth': 0,
                'persist-credentials': False,
            },
        )
        verify_checkout = next(
            step for step in notify_steps
            if step.get('name') == 'Verify the exact producer helper checkout'
        )
        self.assertEqual(
            verify_checkout['env']['EXPECTED_PRODUCER_REVISION'],
            '${{ needs.release_qualification.outputs.producer_revision }}',
        )
        self.assertIn(
            'test "$(git -C producer-source rev-parse HEAD)" = "$EXPECTED_PRODUCER_REVISION"',
            verify_checkout['run'],
        )
        dispatch = next(
            step for step in notify_steps
            if step.get('name') == 'Dispatch exact merged Integration identity to Site'
        )
        script = dispatch['run']
        self.assertIn('python3 producer-source/scripts/build_integration_site_dispatch_payload.py', script)
        self.assertNotIn('python3 scripts/build_integration_site_dispatch_payload.py', script)
        self.assertIn('--output "$PAYLOAD_FILE"', script)
        self.assertIn('gh api repos/TakashiSasaki/templates/dispatches', script)
        self.assertIn('--method POST', script)
        self.assertIn('--input "$PAYLOAD_FILE"', script)
        self.assertLess(script.index('build_integration_site_dispatch_payload.py'), script.index('gh api '))
        self.assertNotRegex(script, r'client_payload\s*\[')
        self.assertNotIn('-f client_payload', script)
        self.assertLess(
            next(index for index, step in enumerate(notify_steps) if step is checkout),
            next(index for index, step in enumerate(notify_steps) if step is verify_checkout),
        )
        self.assertLess(
            next(index for index, step in enumerate(notify_steps) if step is verify_checkout),
            next(index for index, step in enumerate(notify_steps) if step is dispatch),
        )
        expected_bindings = {
            'PRODUCER_SHA': '${{ needs.release_qualification.outputs.producer_revision }}',
            'BUNDLE_SCHEMA': '${{ needs.release_qualification.outputs.bundle_schema }}',
            'BUNDLE_IDENTITY': '${{ needs.release_qualification.outputs.bundle_identity }}',
            'CONTENT_DIGEST': '${{ needs.release_qualification.outputs.bundle_content_digest }}',
            'ARTIFACT_ID': '${{ needs.release_qualification.outputs.artifact_id }}',
            'ARTIFACT_DIGEST': '${{ needs.release_qualification.outputs.artifact_digest }}',
            'ARTIFACT_NAME': '${{ needs.release_qualification.outputs.artifact_name }}',
            'RUN_ID': '${{ needs.release_qualification.outputs.workflow_run_id }}',
            'ATTEMPT': '${{ needs.release_qualification.outputs.workflow_attempt }}',
            'PR_NUMBER': '${{ github.event.pull_request.number }}',
            'WORKFLOW_HEAD': '${{ needs.release_qualification.outputs.workflow_head }}',
            'WORKFLOW_NAME': '${{ needs.release_qualification.outputs.workflow_name }}',
            'WORKFLOW_EVENT': '${{ needs.release_qualification.outputs.workflow_event }}',
            'QUALIFICATION_ARTIFACT_ID': '${{ needs.release_qualification.outputs.qualification_artifact_id }}',
            'QUALIFICATION_ARTIFACT_DIGEST': '${{ needs.release_qualification.outputs.qualification_artifact_digest }}',
            'QUALIFICATION_ARTIFACT_NAME': '${{ needs.release_qualification.outputs.qualification_artifact_name }}',
            'VERIFIED_RECEIPT_DIGEST': '${{ needs.verify_release.outputs.receipt_digest }}',
            'VERIFIED_RECEIPT_ARTIFACT_ID': '${{ needs.verify_release.outputs.artifact_id }}',
            'VERIFIED_RECEIPT_ARTIFACT_DIGEST': '${{ needs.verify_release.outputs.artifact_digest }}',
            'VERIFIED_RECEIPT_ARTIFACT_NAME': '${{ needs.verify_release.outputs.artifact_name }}',
        }
        self.assertEqual(dispatch['env'], {'GH_TOKEN': '${{ secrets.PUBLICATION_AUTOMATION_TOKEN }}', **expected_bindings})

        environment = {
            'PRODUCER_SHA': 'a' * 40,
            'BUNDLE_SCHEMA': '4',
            'BUNDLE_IDENTITY': 'b' * 64,
            'CONTENT_DIGEST': 'c' * 64,
            'ARTIFACT_ID': '11018626853',
            'ARTIFACT_DIGEST': 'sha256:' + 'd' * 64,
            'ARTIFACT_NAME': 'publication-bundle-v4',
            'RUN_ID': '36536060040',
            'ATTEMPT': '1',
            'WORKFLOW_HEAD': 'e' * 40,
            'WORKFLOW_NAME': 'Notify Site after Integration adoption',
            'WORKFLOW_EVENT': 'pull_request',
            'QUALIFICATION_ARTIFACT_ID': '11018217633',
            'QUALIFICATION_ARTIFACT_DIGEST': 'sha256:' + 'f' * 64,
            'QUALIFICATION_ARTIFACT_NAME': 'publication-qualification-v4',
            'VERIFIED_RECEIPT_DIGEST': '1' * 64,
            'VERIFIED_RECEIPT_ARTIFACT_ID': '11019100564',
            'VERIFIED_RECEIPT_ARTIFACT_DIGEST': 'sha256:' + '2' * 64,
            'VERIFIED_RECEIPT_ARTIFACT_NAME': 'publication-verification-v4',
            'PR_NUMBER': '1099',
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'dispatch.json'
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / 'scripts/build_integration_site_dispatch_payload.py'),
                    '--output',
                    str(output),
                ],
                capture_output=True,
                text=True,
                env={**os.environ, **environment},
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            body = output.read_bytes()
            request = json.loads(body)

        self.assertEqual(request['event_type'], 'publication.integration-promoted')
        payload = request['client_payload']
        self.assertEqual(set(payload), {'schema_version', 'boundary', 'release'})
        self.assertEqual(len(payload), 3)
        self.assertEqual(payload['schema_version'], 1)
        self.assertEqual(payload['boundary'], 'integration-to-site')
        release = payload['release']
        self.assertEqual(set(release), {
            'integration_revision', 'bundle', 'workflow', 'qualification_artifact',
            'verified_receipt', 'source_pr',
        })
        self.assertEqual(release['integration_revision'], environment['PRODUCER_SHA'])
        self.assertEqual(release['bundle'], {
            'schema': environment['BUNDLE_SCHEMA'],
            'identity': environment['BUNDLE_IDENTITY'],
            'content_digest': environment['CONTENT_DIGEST'],
            'artifact': {
                'id': environment['ARTIFACT_ID'],
                'digest': environment['ARTIFACT_DIGEST'],
                'name': environment['ARTIFACT_NAME'],
            },
        })
        self.assertEqual(release['workflow'], {
            'run_id': environment['RUN_ID'],
            'attempt': environment['ATTEMPT'],
            'head': environment['WORKFLOW_HEAD'],
            'name': environment['WORKFLOW_NAME'],
            'event': environment['WORKFLOW_EVENT'],
        })
        self.assertEqual(release['qualification_artifact'], {
            'id': environment['QUALIFICATION_ARTIFACT_ID'],
            'digest': environment['QUALIFICATION_ARTIFACT_DIGEST'],
            'name': environment['QUALIFICATION_ARTIFACT_NAME'],
        })
        self.assertEqual(release['verified_receipt'], {
            'digest': environment['VERIFIED_RECEIPT_DIGEST'],
            'artifact': {
                'id': environment['VERIFIED_RECEIPT_ARTIFACT_ID'],
                'digest': environment['VERIFIED_RECEIPT_ARTIFACT_DIGEST'],
                'name': environment['VERIFIED_RECEIPT_ARTIFACT_NAME'],
            },
        })
        self.assertEqual(release['source_pr'], environment['PR_NUMBER'])
        self.assertLess(len(body), 16 * 1024)

    def test_notify_payload_validation_fails_before_creating_request_body(self):
        environment = {
            'PRODUCER_SHA': 'a' * 40,
            'BUNDLE_SCHEMA': '4',
            'BUNDLE_IDENTITY': 'b' * 64,
            'CONTENT_DIGEST': 'c' * 64,
            'ARTIFACT_ID': '11018626853',
            'ARTIFACT_DIGEST': 'sha256:' + 'd' * 64,
            'ARTIFACT_NAME': 'publication-bundle-v4',
            'RUN_ID': '36536060040',
            'ATTEMPT': '1',
            'WORKFLOW_HEAD': 'e' * 40,
            'WORKFLOW_NAME': 'Notify Site after Integration adoption',
            'WORKFLOW_EVENT': 'pull_request',
            'QUALIFICATION_ARTIFACT_ID': '11018217633',
            'QUALIFICATION_ARTIFACT_DIGEST': 'sha256:' + 'f' * 64,
            'QUALIFICATION_ARTIFACT_NAME': 'publication-qualification-v4',
            'VERIFIED_RECEIPT_DIGEST': '1' * 64,
            'VERIFIED_RECEIPT_ARTIFACT_ID': '11019100564',
            'VERIFIED_RECEIPT_ARTIFACT_DIGEST': 'sha256:' + '2' * 64,
            'VERIFIED_RECEIPT_ARTIFACT_NAME': 'publication-verification-v4',
            'PR_NUMBER': '1099',
        }
        environment.pop('VERIFIED_RECEIPT_ARTIFACT_ID')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'dispatch.json'
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / 'scripts/build_integration_site_dispatch_payload.py'),
                    '--output',
                    str(output),
                ],
                capture_output=True,
                text=True,
                env={**os.environ, **environment},
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_promotion_job_conditions_parse_as_complete_actions_expressions(self):
        workflow = yaml.safe_load(
            (ROOT / '.github/workflows/integration-promotion-notify.yml').read_text()
        )
        for name in (
            'validate_promotion_intent',
            'release_qualification',
            'verify_release',
            'notify',
        ):
            with self.subTest(job=name):
                condition = workflow['jobs'][name]['if']
                validate_actions_if_expression(condition)
                for dangling_operator in ('&&', '||'):
                    with self.subTest(dangling_operator=dangling_operator):
                        with self.assertRaises(SyntaxError):
                            validate_actions_if_expression(
                                f'{condition} {dangling_operator}'
                            )

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
        intent_download = next(
            step for step in promote_steps
            if step.get('name') == 'Download the exact trusted promotion intent'
        )
        self.assertTrue(intent_download['with'].get('merge-multiple'))
        self.assertIn('publication_promotion_intent.py verify', promote_commands)
        self.assertIn('publication-promotion-intent.json', promote_commands)
        self.assertIn("needs.controller.outputs.classification == 'AUTO_PROCESSABLE'", reconcile['jobs']['promote_lock_pr']['if'])

        build_step = next(
            step for step in controller_steps
            if step.get('name') == 'Build the deterministic trusted promotion intent'
        )
        self.assertEqual(
            build_step['env']['RECONCILIATION_WORKFLOW_REPOSITORY'],
            '${{ job.workflow_repository }}',
        )
        self.assertEqual(
            build_step['env']['RECONCILIATION_WORKFLOW_FILE_PATH'],
            '${{ job.workflow_file_path }}',
        )
        self.assertEqual(
            build_step['env']['RECONCILIATION_WORKFLOW_REF'],
            '${{ job.workflow_ref }}',
        )
        self.assertEqual(
            build_step['env']['RECONCILIATION_WORKFLOW_SHA'],
            '${{ job.workflow_sha }}',
        )
        self.assertIn('--run-workflow-path "$RUN_WORKFLOW_PATH"', build_step['run'])
        self.assertIn('--reconciliation-workflow-sha "$RECONCILIATION_WORKFLOW_SHA"', build_step['run'])
        self.assertNotIn('inputs.reconciliation_workflow', reconcile)
        self.assertIn('publication_promotion_intent.py verify-target', promote_commands)
        self.assertIn('--expected-reconciliation-workflow-sha "$EXPECTED_RECONCILIATION_WORKFLOW_SHA"', promote_commands)
        self.assertIn('--expected-intent-digest "$PROMOTION_INTENT_DIGEST"', promote_commands)

        notify = yaml.safe_load((ROOT / '.github/workflows/integration-promotion-notify.yml').read_text())
        self.assertIn('validate_promotion_intent', notify['jobs'])
        self.assertIn('verify-merged', '\n'.join(step.get('run', '') for step in notify['jobs']['validate_promotion_intent']['steps']))
        self.assertIn('needs.validate_promotion_intent.result == \'success\'', notify['jobs']['release_qualification']['if'])

    def test_promotion_intent_staging_allows_regular_create_and_rejects_mode_changes(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/integration-reconcile.yml').read_text())
        step = next(
            step for step in workflow['jobs']['promote_lock_pr']['steps']
            if step.get('name') == 'Add the deterministic promotion intent'
        )

        def run_staging_step(intent_mode):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                integration_base = root / 'integration-base'
                integration_base.mkdir()
                subprocess.run(['git', '-C', str(integration_base), 'init', '-q'], check=True)
                subprocess.run(['git', '-C', str(integration_base), 'config', 'user.name', 'Test'], check=True)
                subprocess.run(['git', '-C', str(integration_base), 'config', 'user.email', 'test@example.invalid'], check=True)
                (integration_base / 'publication-sources.json').write_text('{}\n', encoding='utf-8')
                subprocess.run(['git', '-C', str(integration_base), 'add', 'publication-sources.json'], check=True)
                subprocess.run(['git', '-C', str(integration_base), 'commit', '-m', 'base'], check=True, capture_output=True)

                intent_dir = root / 'promotion-intent'
                intent_dir.mkdir()
                intent = intent_dir / 'publication-promotion-intent.json'
                intent.write_text('{"intent":true}\n', encoding='utf-8')
                intent.chmod(intent_mode)
                environment = {**os.environ, 'LOCK_UPDATE_REQUIRED': 'false'}
                return subprocess.run(
                    ['bash', '-e', '-o', 'pipefail', '-c', step['run']],
                    cwd=root,
                    env=environment,
                    text=True,
                    capture_output=True,
                )

        regular_file = run_staging_step(0o644)
        self.assertEqual(regular_file.returncode, 0, regular_file.stdout + regular_file.stderr)
        executable_file = run_staging_step(0o755)
        self.assertNotEqual(executable_file.returncode, 0)

    def test_promotion_intent_schema_split_preserves_run_path_and_notification_contract(self):
        reconcile_text = (ROOT / '.github/workflows/integration-reconcile.yml').read_text()
        self.assertIn(
            'RUN_WORKFLOW_PATH=".github/workflows/${GITHUB_WORKFLOW_REF#*/.github/workflows/}"',
            reconcile_text,
        )
        self.assertIn('--workflow-path "$WORKFLOW_PATH"', reconcile_text)
        self.assertIn('--run-workflow-path "$RUN_WORKFLOW_PATH"', reconcile_text)

        source = (ROOT / 'scripts/publication_promotion_intent.py').read_text()
        self.assertIn('"run_provenance"', source)
        self.assertIn('"reconciliation_implementation"', source)
        self.assertIn('RECONCILIATION_WORKFLOW_PATH = ".github/workflows/integration-reconcile.yml"', source)
        self.assertNotIn('qualification.workflow_path', source)

        notify = (ROOT / '.github/workflows/integration-promotion-notify.yml').read_text()
        self.assertIn('publication_promotion_intent.py verify-merged-pr', notify)
        self.assertIn('--workflow-path "$WORKFLOW_PATH"', notify)
        self.assertNotIn('reconciliation_implementation', notify)

    def test_fail_closed_path_previews_schema_two_provenance_without_upload_or_pr(self):
        reconcile = yaml.safe_load((ROOT / '.github/workflows/integration-reconcile.yml').read_text())
        controller_steps = reconcile['jobs']['controller']['steps']
        classify = next(step for step in controller_steps if step.get('name') == 'Classify the guarded reconciliation transaction')
        preview = next(step for step in controller_steps if step.get('name') == 'Validate schema-2 provenance without authorizing mutations')
        build = next(step for step in controller_steps if step.get('name') == 'Build the deterministic trusted promotion intent')

        self.assertIn('reason_code=', classify['run'])
        self.assertIn("outputs.classification == 'NOT_ELIGIBLE'", preview['if'])
        self.assertIn("outputs.reason_code == 'AUTHORIZATION_NOT_GRANTED'", preview['if'])
        self.assertIn("outputs.reason_code == 'KILL_SWITCH_ACTIVE'", preview['if'])
        self.assertIn('publication_promotion_intent.py preview', preview['run'])
        self.assertIn('--github-summary "$GITHUB_STEP_SUMMARY"', preview['run'])
        self.assertNotIn('upload-artifact', preview.get('uses', ''))
        self.assertNotIn('gh pr create', preview['run'])
        self.assertIn("steps.reconcile.outputs.classification == 'AUTO_PROCESSABLE'", build['if'])

    def test_bundle_receipt_uses_github_workflow_path_shape(self):
        for name, expected_count in (
            ('integration-reconcile.yml', 2),
            ('integration-promotion-notify.yml', 1),
        ):
            workflow = (ROOT / '.github/workflows' / name).read_text()
            with self.subTest(workflow=name):
                self.assertEqual(
                    sum(
                        line.strip().startswith(
                            'WORKFLOW_PATH=".github/workflows/${GITHUB_WORKFLOW_REF#*/.github/workflows/}"'
                        )
                        for line in workflow.splitlines()
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
