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

