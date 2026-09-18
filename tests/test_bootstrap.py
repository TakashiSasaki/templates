import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

class BootstrapTests(unittest.TestCase):
    def test_independent_history_and_exact_reviewed_locks(self):
        proof=json.loads((ROOT/'bootstrap/provenance.json').read_text())
        lock=json.loads((ROOT/'publication-sources.json').read_text())
        roots=subprocess.check_output(['git','rev-list','--max-parents=0','HEAD'],cwd=ROOT,text=True).split()
        self.assertEqual(roots,[proof['initial_integration_revision']])
        self.assertNotEqual(roots[0],proof['source_site_revision'])
        for revision in (proof['source_site_revision'],*proof['reviewed_providers'].values()):self.assertRegex(revision,r'\A[0-9a-f]{40}\Z')
        reference=json.loads((ROOT/'bootstrap/site-bundle-reference.json').read_text())
        self.assertEqual(proof['reviewed_providers'],reference['providers'])
        self.assertEqual(lock['schema_version'], 2)
        self.assertEqual(set(lock['publications']),{'modeling','composition','policy'})
        for provider in lock['publications'].values():
            self.assertEqual(set(provider),{'revision'})
            self.assertRegex(provider['revision'],r'\A[0-9a-f]{40}\Z')
        self.assertEqual(set(proof['reviewed_providers']),{'composition','policy'})
        self.assertFalse(proof['site_adoption']);self.assertFalse(proof['deployment'])

    def test_current_topology_preserves_explicit_downstream_adoption(self):
        authority=json.loads((ROOT/'authority.json').read_text())
        self.assertEqual(authority['authority'],'integration')
        self.assertFalse(authority['automatic_provider_following'])
        self.assertEqual(authority['output_contract'],'Integrated Publication Bundle v4')
        self.assertEqual(authority['historical_output_contracts'],['Integrated Publication Bundle v3'])
        adoption=authority['automatic_site_adoption']
        self.assertEqual(adoption['capability'],'guarded-preauthorized-controller-path')
        self.assertEqual(adoption['default_mode'],'shadow')
        self.assertTrue(adoption['authorization_required'])
        self.assertEqual(authority['deployment_authority'],'site')
        self.assertIn('explicitly reviewed exact Integration release',authority['site_upstream'])
        self.assertIn('Site selects an explicitly reviewed exact Integration release',authority['site_upstream'])
        self.assertIn('release alone is not Site-adoption authorization',authority['site_upstream'])
        self.assertNotIn('has not adopted',(ROOT/'README.md').read_text())
