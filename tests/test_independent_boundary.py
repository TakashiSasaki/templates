import ast
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]

class IndependentBoundaryTests(unittest.TestCase):
    def test_no_site_implementation_or_provider_source_copies(self):
        for name in ('site_renderer','assets','translations','src/agent_policy','components','recipes'):
            self.assertFalse((ROOT/name).exists(),name)
        for package in ('integration','publication_bundle'):
            for path in (ROOT/package).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_text())):
                    names=([node.module or ''] if isinstance(node,ast.ImportFrom) else [a.name for a in node.names] if isinstance(node,ast.Import) else [])
                    for name in names:self.assertNotIn(name.split('.')[0],{'site_renderer','scripts'},str(path))

    def test_producer_cli_runs_in_independent_checkout(self):
        result=subprocess.run([sys.executable,'scripts/produce_publication_bundle.py','--help'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('--integration-root',result.stdout)
        self.assertNotIn('--site-root',result.stdout)
