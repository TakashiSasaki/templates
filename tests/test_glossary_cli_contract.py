from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.generate_glossary import _mapping, generate
from scripts.glossary import GlossaryError, load_glossary


VALID_EXTERNAL = """schema_version: 1
terms:
  - id: external-git-branch
    term: Branch
    origin: external
    summary: A named line of development in Git.
    authority:
      kind: upstream
      sources:
        - title: Git glossary
          url: https://git-scm.com/docs/gitglossary
"""


class GlossaryCliContractTests(unittest.TestCase):
    def load_text(self, text: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "glossary.yml"
            path.write_text(text, encoding="utf-8")
            return load_glossary(path)

    def test_valid_external_term_loads_successfully(self) -> None:
        terms = self.load_text(VALID_EXTERNAL)
        self.assertEqual(len(terms), 1)
        self.assertEqual(terms[0]["id"], "external-git-branch")
        self.assertEqual(terms[0]["origin"], "external")
        self.assertEqual(terms[0]["authority"]["kind"], "upstream")

    def test_authority_optional_version_and_locator_are_preserved(self) -> None:
        text = VALID_EXTERNAL.replace(
            "          url: https://git-scm.com/docs/gitglossary\n",
            "          url: https://git-scm.com/docs/gitglossary\n"
            "          version: '2.0'\n"
            "          locator: glossary-entry\n",
        )
        terms = self.load_text(text)
        source = terms[0]["authority"]["sources"][0]
        self.assertEqual(source["version"], "2.0")
        self.assertEqual(source["locator"], "glossary-entry")

    def test_invalid_related_term_id_is_rejected(self) -> None:
        text = """schema_version: 1
terms:
  - id: templates-example
    term: Example
    origin: repository
    definition: Example term.
    related_terms:
      - invalid_id!
"""
        with self.assertRaisesRegex(GlossaryError, "contains an invalid term ID"):
            self.load_text(text)

    def test_mapping_rejects_missing_separator(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "name=value syntax"):
            _mapping(["site"], "publication")

    def test_mapping_rejects_empty_name(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "non-empty name=value syntax"):
            _mapping(["=/tmp/site"], "publication")

    def test_mapping_rejects_empty_value(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "non-empty name=value syntax"):
            _mapping(["site="], "publication")

    def test_mapping_rejects_duplicate_provider(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "duplicate publication provider"):
            _mapping(["site=one", "site=two"], "publication")

    def test_generate_wraps_missing_publication_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(
                GlossaryError,
                "unable to resolve glossary publication input",
            ):
                generate(
                    [f"site={root / 'missing'}"],
                    ["site=" + "a" * 40],
                    "TakashiSasaki/templates",
                    root / "out.json",
                )


if __name__ == "__main__":
    unittest.main()
