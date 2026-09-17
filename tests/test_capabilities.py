from pathlib import Path
import json
import tempfile
import unittest

from integration.capabilities import CapabilityError, validate_catalog_closure, validate_provider_declaration

class CapabilityTests(unittest.TestCase):
    def test_provider_declarations_are_bound_to_registry(self):
        for provider in ("modeling", "composition", "policy"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "docs").mkdir()
                (root / "docs/publication-capabilities.json").write_text(
                    json.dumps({
                        "schema_version": 1,
                        "provider": provider,
                        "protocol": "publication-bundle",
                        "exports": [{
                            "kind": "document",
                            "namespace": f"{provider}.fixture",
                            "media_type": "text/markdown",
                            "identity_basis": "fixture",
                            "feature": "publication.generic-document.v1",
                            "rights": "allowlisted",
                        }],
                        "requirements": [{
                            "feature": "publication.generic-document.v1",
                            "required": True,
                            "fallback": "generic-document",
                        }],
                    }),
                    encoding="utf-8",
                )
                with self.subTest(provider=provider):
                    declaration = validate_provider_declaration(root, provider)
                    self.assertEqual(declaration["provider"], provider)

    def test_invalid_declaration_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "docs"
            path.mkdir()
            (path / "publication-capabilities.json").write_text(
                json.dumps({"schema_version": 1, "provider": "modeling", "protocol": "wrong", "exports": [], "requirements": []}),
                encoding="utf-8",
            )
            with self.assertRaises(CapabilityError):
                validate_provider_declaration(root, "modeling")

    def test_catalog_closure_requires_an_export_kind(self):
        declaration = {"provider": "modeling", "exports": [{"kind": "record"}]}
        with self.assertRaises(CapabilityError):
            validate_catalog_closure(declaration, document_count=1, asset_count=0)


if __name__ == "__main__":
    unittest.main()
