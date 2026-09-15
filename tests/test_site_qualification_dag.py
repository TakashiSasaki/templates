"""DAG coverage, trust bindings and failure propagation at the scheduling boundary."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import yaml
from scripts.consume_site_build_artifact import validate_binding
from scripts.site_build_artifact import ArtifactError
from scripts.verify_site_full_qualification import REQUIRED_SUITES

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / name).read_text())


class QualificationDagTests(unittest.TestCase):
    def test_complete_suite_mapping_and_no_core_serial_barrier(self):
        jobs = workflow('build-pages.yml')['jobs']
        gate = jobs['full_qualification']
        # pull_request events have no workflow_call inputs: an empty string is not a boolean.
        self.assertEqual(jobs['build']['with']['reuse_pr_build'], '${{ inputs.reuse_pr_build || false }}')
        self.assertNotIn('core_tests', jobs['build']['needs'])
        self.assertNotIn('build', jobs['core_tests']['needs'])
        self.assertEqual(jobs['build']['uses'], './.github/workflows/site-producer.yml')
        for consumer in ('reference_consumer', 'cross_authority'):
            self.assertIn('build', jobs[consumer]['needs'])
            self.assertNotIn('check', jobs[consumer]['needs'])
            for key in ('artifact_id', 'artifact_digest', 'build_inputs'):
                self.assertEqual(jobs[consumer]['with'][key], '${{ needs.build.outputs.' + key + ' }}')
        names = {}
        for jobid, job in jobs.items():
            if 'uses' in job:
                child = workflow(job['uses'].rsplit('/', 1)[1])
                for childid, childjob in child['jobs'].items():
                    names[job.get('name', jobid) + ' / ' + childjob.get('name', childid)] = jobid
            else:
                names[job.get('name', jobid)] = jobid
        for suite in REQUIRED_SUITES:
            self.assertEqual(suite.workflow_path, '.github/workflows/build-pages.yml')
            self.assertIn(suite.job_name, names, suite.key)
            self.assertIn(names[suite.job_name], gate['needs'], suite.key)

    def test_standalone_producer_keeps_full_suite_without_serializing_pr_core(self):
        producer = workflow('site-producer.yml')
        self.assertFalse(producer[True]['workflow_call']['inputs']['core_tests_scheduled']['default'])
        step = next(s for s in producer['jobs']['build']['steps'] if s['name'] == 'Run site assembly tests')
        self.assertIn('--check integration-tests', step['run'])
        self.assertIn('--check unit-tests', step['run'])
        jobs = workflow('build-pages.yml')['jobs']
        self.assertEqual(jobs['build']['with']['core_tests_scheduled'],
                         "${{ inputs.site_ref == '' && needs.classify_browser.result == 'success' }}")
        self.assertNotIn('core_tests', jobs['build']['needs'])
        self.assertIn('core_tests', jobs['validate']['needs'])

    def test_gate_rejects_failed_cancelled_skipped_pending_and_missing_results(self):
        gate = workflow('build-pages.yml')['jobs']['full_qualification']
        script = gate['steps'][0]['run']
        body = script.split("<<'PYCODE'\n", 1)[1].rsplit('PYCODE', 1)[0]
        success = {name: {'result': 'success'} for name in gate['needs']}
        for result in ('success', 'failure', 'cancelled', 'skipped', 'pending', ''):
            data = copy.deepcopy(success)
            data['cross_authority']['result'] = result
            completed = subprocess.run([sys.executable, '-c', body], env={**os.environ, 'RESULTS': json.dumps(data)}, capture_output=True)
            self.assertEqual(completed.returncode == 0, result == 'success', result)
        del success['build']
        completed = subprocess.run([sys.executable, '-c', body], env={**os.environ, 'RESULTS': json.dumps(success)}, capture_output=True)
        self.assertNotEqual(completed.returncode, 0)


    def test_producer_and_consumers_never_wait_for_another_workflow(self):
        producer = workflow('site-producer.yml')
        self.assertNotIn('concurrency', producer)
        source = (ROOT / 'scripts/site_build_artifact.py').read_text()
        self.assertIn('wait=False) if eligible or canonical', source)
        for name in ('reference-consumer.yml', 'site-composition-playground-cross-authority.yml'):
            text = (ROOT / '.github/workflows' / name).read_text()
            self.assertNotIn('uses: ./.github/workflows/build-pages.yml', text)
            self.assertNotIn('uses: ./.github/workflows/site-producer.yml', text)
            self.assertIn('scripts/consume_site_build_artifact.py', text)


class ScheduledArtifactBindingTests(unittest.TestCase):
    def test_binding_family(self):
        digest = 'sha256:' + 'd' * 64
        expected = dict(site='a'*40, composition='b'*40, policy='c'*40, repository='owner/repo', staging='', staging_ids='', deployment_timestamp='')
        metadata = dict(id=123, expired=False, digest=digest, workflow_run=dict(id=456, head_sha='a'*40))
        args = dict(artifact_id=123, archive_digest=digest, run_id=456, head='a'*40,
                    repository='owner/repo', locked={'composition':'b'*40, 'policy':'c'*40})
        validate_binding(metadata, expected, **args)
        for field, value in [('site', 'f'*40), ('composition', 'f'*40), ('policy', 'f'*40), ('repository', 'other/repo'), ('staging', 'candidate')]:
            changed = {**expected, field: value}
            with self.subTest(input=field), self.assertRaises(ArtifactError):
                validate_binding(metadata, changed, **args)
        for field, value in [('id',124), ('expired',True), ('digest','sha256:'+'e'*64), ('workflow_run',{'id':457,'head_sha':'a'*40})]:
            with self.subTest(metadata=field), self.assertRaises(ArtifactError):
                validate_binding({**metadata, field:value}, expected, **args)
