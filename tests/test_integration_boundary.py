"""Regression guards for the internal authority dependency direction."""
import ast
from pathlib import Path
import unittest
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


class BoundaryTests(unittest.TestCase):
    def test_integration_has_no_site_implementation_imports(self):
        for path in (ROOT / 'integration').rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                names = []
                if isinstance(node, ast.Import):
                    names = [item.name for item in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or '']
                for name in names:
                    self.assertFalse(name.startswith(('scripts.', 'site_renderer')),
                                     f'{path}: forbidden dependency {name}')

    def test_renderer_has_no_integration_implementation_imports(self):
        for path in (ROOT / 'site_renderer').rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                names = ([item.name for item in node.names] if isinstance(node, ast.Import)
                         else [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
                for name in names:
                    self.assertFalse(name.startswith('integration'), str(path))

    def test_deployment_requires_explicit_site_dispatch(self):
        workflow = (ROOT / '.github/workflows/deploy-pages.yml').read_text()
        self.assertIn('  workflow_dispatch:', workflow)
        self.assertNotIn('  push:', workflow)
        self.assertEqual(workflow.count("github.event_name == 'workflow_dispatch'"), 3)
        self.assertEqual(workflow.count("github.ref == 'refs/heads/site'"), 3)

    def test_definition_only_adapters_preserve_direct_execution(self):
        modules = ('glossary', 'publish_translations', 'reader_navigation_locales',
                   'translation_coverage', 'translation_fragment_reconciliation',
                   'translation_link_identity', 'translation_link_selection',
                   'translation_manifest')
        for module in modules:
            for invocation in ([str(ROOT/'scripts'/f'{module}.py')], ['-m', 'scripts.'+module]):
                with self.subTest(module=module,invocation=invocation):
                    result=subprocess.run([sys.executable,*invocation],cwd=ROOT,capture_output=True,text=True)
                    self.assertEqual(result.returncode,0,result.stderr)

    def test_shared_contract_has_no_implementation_imports(self):
        for path in (ROOT/'publication_bundle').rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                names=([x.name for x in node.names] if isinstance(node,ast.Import)
                       else [node.module or ''] if isinstance(node,ast.ImportFrom) else [])
                for name in names:
                    self.assertFalse(name.startswith(('integration','site_renderer','scripts')),f'{path}: {name}')
