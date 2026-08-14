from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.glossary import GlossaryError, glossary_source_from_catalog, load_glossary


EXTERNAL_TEMPLATE = """schema_version: 1
terms:
  - id: external-web-example
    term: Example
    origin: external
    summary: Example external term.
    authority:
      kind: upstream
      sources:
        - title: Example authority
          url: {url}
"""


class GlossaryCodexRegressionTests(unittest.TestCase):
    def load_text(self, text: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "glossary.yml"
            path.write_text(text, encoding="utf-8")
            load_glossary(path)

    def test_decoded_yaml_control_character_is_rejected(self) -> None:
        text = """schema_version: 1
terms:
  - id: templates-decoded-control
    term: "Bad\\x00label"
    origin: repository
    definition: Example.
"""
        with self.assertRaisesRegex(GlossaryError, "disallowed control character"):
            self.load_text(text)

    def test_malformed_bracketed_authority_host_is_schema_error(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "valid absolute HTTPS URL"):
            self.load_text(EXTERNAL_TEMPLATE.format(url="https://[bad/path"))

    def test_out_of_range_authority_port_is_schema_error(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "valid absolute HTTPS URL"):
            self.load_text(
                EXTERNAL_TEMPLATE.format(url="https://example.com:99999/path")
            )

    def test_invalid_dns_authority_host_is_rejected(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "invalid authority host"):
            self.load_text(
                EXTERNAL_TEMPLATE.format(url="https://exa_mple.com/path")
            )

    def test_symlinked_publication_catalog_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "provider"
            docs = root / "docs"
            docs.mkdir(parents=True)
            outside = Path(directory) / "outside-catalog.json"
            outside.write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "documents": [],
                    }
                ),
                encoding="utf-8",
            )
            catalog = docs / "publication-catalog.json"
            try:
                catalog.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are not supported in this environment")
            with self.assertRaisesRegex(GlossaryError, "must not traverse a symlink"):
                glossary_source_from_catalog(root)


if __name__ == "__main__":
    unittest.main()
