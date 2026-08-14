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
    def test_valid_external_term_loads_successfully(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "glossary.yml"
            path.write_text(VALID_EXTERNAL, encoding="utf-8")
            terms = load_glossary(path)
        self.assertEqual(len(terms), 1)
        self.assertEqual(terms[0]["id"], "external-git-branch")
        self.assertEqual(terms[0]["origin"], "external")
        self.assertEqual(terms[0]["authority"]["kind"], "upstream")

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
