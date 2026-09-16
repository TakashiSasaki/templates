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
        self.assertEqual(proof['reviewed_providers'],{k:v['revision'] for k,v in lock['publications'].items()})
        self.assertEqual(set(proof['reviewed_providers']),{'composition','policy'})
        self.assertFalse(proof['site_adoption']);self.assertFalse(proof['deployment'])

    def test_transition_does_not_claim_site_adoption(self):
        authority=json.loads((ROOT/'authority.json').read_text())
        self.assertEqual(authority['authority'],'integration')
        self.assertFalse(authority['automatic_provider_following'])
        self.assertFalse(authority['automatic_site_adoption'])
        self.assertEqual(authority['deployment_authority'],'site')
        self.assertIn('no adoption',authority['site_upstream'])
