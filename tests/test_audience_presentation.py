"""Assembled presentation boundaries, including services without document identities."""
import json
from pathlib import Path
import tempfile
import unittest
from scripts.audience_context import create_resolver
from scripts.audience_presentation import attach_shell, finalize_presentation


class AudiencePresentationTests(unittest.TestCase):
    def test_navigation_covers_memberships_once_per_declared_projection(self):
        model = create_resolver().export_runtime_map()
        for audience, nodes in model['navigation'].items():
            destinations = set()
            def visit(nodes):
                for node in nodes:
                    if 'children' in node:
                        visit(node['children'])
                    else:
                        destinations.add(node['destination'])
                        self.assertEqual(model['routes'][node['href']], node['destination'])
            visit(nodes)
            self.assertEqual(destinations, {d for d,doc in model['documents'].items() if audience in doc['audiences']})

    def test_shared_service_inventory_is_exact_and_does_not_create_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = create_resolver().export_runtime_map()
            (root/'audience-runtime.json').write_text(json.dumps(model))
            doc = root/'index.html'; service = root/'files'/'example.html'; error = root/'404.html'
            service.parent.mkdir()
            source = '<html><head></head><body><main>Content</main></body></html>'
            updates = {doc:source, service:source, error:source}
            finalize_presentation(root,updates)
            result = json.loads((root/'audience-runtime.json').read_text())
            self.assertEqual(result['services'], ['/files/example.html'])
            self.assertEqual(result['documents'], model['documents'])
            self.assertIn('audience-shell.js',updates[service])
            self.assertNotIn('audience-shell.js',updates[error])
            self.assertEqual(attach_shell(updates[service]), updates[service])

    def test_service_csp_keeps_unrelated_restrictions(self):
        source = '<head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"></head>'
        result = attach_shell(source)
        from html import unescape
        result = unescape(result)
        for directive in ["default-src 'none'", "base-uri 'none'", "form-action 'none'", "script-src 'self'", "connect-src 'self'", "style-src 'unsafe-inline' 'self'"]:
            self.assertIn(directive,result)
        self.assertNotIn("script-src 'unsafe-inline'",result)

    def test_source_text_mention_is_not_a_loaded_controller(self):
        source = '<head></head><body><main><code>javascripts/audience-context.js</code></main></body>'
        result = attach_shell(source)
        self.assertIn('<script src="/javascripts/audience-context.js" defer></script>', result)
        self.assertIn('audience-shell.js', result)
