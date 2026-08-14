from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.glossary import GlossaryError, load_glossary


class GlossaryEnumTypeTests(unittest.TestCase):
    def load_text(self, text: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "glossary.yml"
            path.write_text(text, encoding="utf-8")
            load_glossary(path)

    def test_origin_sequence_is_rejected_as_schema_error(self) -> None:
        with self.assertRaisesRegex(
            GlossaryError,
            "origin must be repository or external",
        ):
            self.load_text(
                """schema_version: 1
terms:
  - id: templates-example
    term: Example
    origin: []
    definition: Example definition.
"""
            )

    def test_origin_mapping_is_rejected_as_schema_error(self) -> None:
        with self.assertRaisesRegex(
            GlossaryError,
            "origin must be repository or external",
        ):
            self.load_text(
                """schema_version: 1
terms:
  - id: templates-example
    term: Example
    origin: {}
    definition: Example definition.
"""
            )

    def test_authority_kind_sequence_is_rejected_as_schema_error(self) -> None:
        with self.assertRaisesRegex(
            GlossaryError,
            "kind must be normative, upstream, or conventional",
        ):
            self.load_text(
                """schema_version: 1
terms:
  - id: external-example-term
    term: Example
    origin: external
    summary: Example summary.
    authority:
      kind: []
      sources:
        - title: Example source
          url: https://example.com/spec
"""
            )

    def test_authority_kind_mapping_is_rejected_as_schema_error(self) -> None:
        with self.assertRaisesRegex(
            GlossaryError,
            "kind must be normative, upstream, or conventional",
        ):
            self.load_text(
                """schema_version: 1
terms:
  - id: external-example-term
    term: Example
    origin: external
    summary: Example summary.
    authority:
      kind: {}
      sources:
        - title: Example source
          url: https://example.com/spec
"""
            )


if __name__ == "__main__":
    unittest.main()
