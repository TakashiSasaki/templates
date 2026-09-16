"""Qualification reachability and asynchronous cadence contracts."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml
from integration.qualification import qualify
from publication_bundle.contract import BundleError
from tests.test_publication_bundle import fixture,finish,PRODUCER,PROVIDERS

ROOT=Path(__file__).resolve().parents[1]


class IntegrationQualificationTests(unittest.TestCase):
    def test_qualification_requires_equivalent_second_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            counter=[]
            def produce(**inputs):
                root=fixture(inputs['output']);counter.append(root)
                if len(counter)==2:(root/'publication/intro.md').write_text('Nondeterministic bytes')
                return finish(root)
            with patch('integration.qualification.produce',side_effect=produce),self.assertRaisesRegex(BundleError,'not deterministic'):
                qualify(output=Path(tmp)/'bundle',producer_revision=PRODUCER['revision'],provider_revisions=PROVIDERS)
            self.assertEqual(len(counter),2)

    def test_qualification_cli_imports_without_site_implementation(self):
        result=subprocess.run([sys.executable,'scripts/qualify_integration.py','--help'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('site-root',result.stdout)

    def test_candidate_workflow_stops_at_bundle_and_preserves_lock(self):
        workflow=yaml.safe_load((ROOT/'.github/workflows/integration-qualification.yml').read_text())
        self.assertEqual(set(workflow['jobs']),{'qualify'})
        text=str(workflow['jobs']['qualify']['steps'])
        for forbidden in ('render_publication_bundle','build-pages.yml','playwright','deploy-pages','advance_publication_source'):
            self.assertNotIn(forbidden,text)
        self.assertIn('qualify_integration.py',text)
        self.assertIn('tests.test_integration_qualification',text)
        self.assertIn('actions/upload-artifact@',text)

    def test_canonical_renderer_job_has_no_provider_checkouts(self):
        workflow=yaml.safe_load((ROOT/'.github/workflows/site-producer.yml').read_text())
        build=workflow['jobs']['build']
        self.assertEqual(build['needs'],'integration')
        self.assertNotIn('composition-source',str(build))
        self.assertNotIn('policy-source',str(build))
        self.assertIn('publication_bundle_artifact.py consume',str(build))
        self.assertIn('render_publication_bundle.py',str(build))

    def test_freshness_does_not_qualify_site(self):
        workflow=yaml.safe_load((ROOT/'.github/workflows/check-publication-freshness.yml').read_text())
        candidate=workflow['jobs']['candidate_build']
        self.assertEqual(candidate['uses'],'./.github/workflows/integration-qualification.yml')
        self.assertNotIn('site_ref',candidate['with'])

    def test_integration_construction_does_not_schedule_site_acceptance(self):
        from scripts.classify_site_ci import classify_paths
        candidate=classify_paths(['integration/producer.py','integration/site-slots.json'])
        self.assertTrue(candidate.integration_required)
        for field in ('build_required','browser_required','pwa_required','reference_consumer_required','cross_authority_required','playground_required'):
            self.assertFalse(getattr(candidate,field),field)
        for paths in (['integration/qualification.py'],['integration/producer.py','.github/workflows/build-pages.yml'],['publication_bundle/contract.py']):
            self.assertTrue(classify_paths(paths).full_required)
        self.assertTrue(classify_paths(['integration/producer.py'],force_full=True).browser_required)

    def test_integration_result_is_required_by_construction_gate(self):
        workflow=yaml.safe_load((ROOT/'.github/workflows/build-pages.yml').read_text())
        job=workflow['jobs']['integration_only']
        self.assertIn("outputs.build_required == 'false'",job['if'])
        gate=workflow['jobs']['validate']
        self.assertIn('integration_only',gate['needs'])
        self.assertIn('test "$INTEGRATION_RESULT" = success',str(gate['steps']))
