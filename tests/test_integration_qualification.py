"""Qualification reachability and asynchronous cadence contracts."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml
from integration.qualification import qualify
from publication_bundle.contract import BundleError
from scripts.build_qualification_report import build_payload
from tests.test_publication_bundle import fixture,finish,PRODUCER,PROVIDERS

ROOT=Path(__file__).resolve().parents[1]


class IntegrationQualificationTests(unittest.TestCase):
    def test_report_builder_accepts_modeling_provider_tuple(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / 'bundle'
            bundle.mkdir()
            (bundle / 'bundle.json').write_text(json.dumps({
                'producer': {'authority': 'integration', 'revision': 'a' * 40},
                'schema_version': 4,
                'identity': 'b' * 64,
                'content_digest': 'c' * 64,
            }))
            (bundle / 'provenance.json').write_text(json.dumps({
                'providers': {
                    'modeling': 'd' * 40,
                    'composition': 'e' * 40,
                    'policy': 'f' * 40,
                },
            }))
            args = argparse.Namespace(
                bundle=bundle,
                integration_revision='a' * 40,
                modeling_root=Path(tmp) / 'modeling',
                composition_root=Path(tmp) / 'composition',
                policy_root=Path(tmp) / 'policy',
                trusted_policy_revision='f' * 40,
                trusted_controller_revision='a' * 40,
                evidence_ref=['local://bundle'],
            )
            with patch('scripts.build_qualification_report._requirements', return_value=[]), \
                 patch('scripts.build_qualification_report._destinations', return_value=['modeling/index.md']):
                payload = build_payload(args)
            self.assertEqual(
                set(payload['candidate']['providers']),
                {'modeling', 'composition', 'policy'},
            )

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
            self.assertFalse((Path(tmp)/'bundle').exists())

    def test_qualification_cli_imports_without_site_implementation(self):
        result=subprocess.run([sys.executable,'scripts/qualify_integration.py','--help'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('site-root',result.stdout)

    def test_reusable_candidate_qualification_reaches_stale_contract_regressions(self):
        workflow=yaml.safe_load((ROOT/'.github/workflows/integration-qualification.yml').read_text())
        commands='\n'.join(step.get('run','') for step in workflow['jobs']['qualify']['steps'])
        self.assertIn('scripts/run_integration_preflight.py fast',commands)
        self.assertNotIn('tests.test_translation_manifest_closure',commands)
        self.assertIn('scripts/qualify_integration.py',commands)
