from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.generate_glossary import generate
from scripts.glossary import (
    GlossaryError,
    glossary_source_from_catalog,
    integrate_glossaries,
    load_glossary,
)


REPO_TERM = """schema_version: 1
terms:
  - id: templates-provider-branch
    term: Provider branch
    aliases:
      - publication provider
    localized_labels:
      ja:
        term: プロバイダーブランチ
        aliases:
          - 提供ブランチ
    origin: repository
    definition: A branch that owns canonical publication content.
"""

EXTERNAL_TERM = """schema_version: 1
terms:
  - id: external-git-branch
    term: Branch
    localized_labels:
      ja:
        term: ブランチ
    origin: external
    summary: A named line of development in Git.
    authority:
      kind: upstream
      sources:
        - title: Git glossary
          url: https://git-scm.com/docs/gitglossary
"""


class GlossarySchemaTests(unittest.TestCase):
    def load_text(self, text: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "glossary.yml"
            path.write_text(text, encoding="utf-8")
            return load_glossary(path)

    def test_repository_term_preserves_japanese_labels(self) -> None:
        terms = self.load_text(REPO_TERM)
        self.assertEqual(
            terms[0]["localized_labels"]["ja"]["term"],
            "プロバイダーブランチ",
        )
        self.assertEqual(
            terms[0]["localized_labels"]["ja"]["aliases"],
            ["提供ブランチ"],
        )

    def test_language_tag_output_is_canonicalized(self) -> None:
        text = REPO_TERM.replace("      ja:\n", "      JA-jp:\n")
        terms = self.load_text(text)
        self.assertIn("ja-JP", terms[0]["localized_labels"])
        self.assertNotIn("JA-jp", terms[0]["localized_labels"])

    def test_external_term_requires_authority(self) -> None:
        text = EXTERNAL_TERM.replace(
            "    authority:\n"
            "      kind: upstream\n"
            "      sources:\n"
            "        - title: Git glossary\n"
            "          url: https://git-scm.com/docs/gitglossary\n",
            "",
        )
        with self.assertRaisesRegex(GlossaryError, "authority is required"):
            self.load_text(text)

    def test_repository_term_rejects_external_namespace(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "must start with templates-"):
            self.load_text(
                REPO_TERM.replace(
                    "templates-provider-branch",
                    "external-git-provider-branch",
                )
            )

    def test_external_term_rejects_repository_namespace(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "external-<domain>-<slug>"):
            self.load_text(
                EXTERNAL_TERM.replace(
                    "external-git-branch",
                    "templates-git-branch",
                )
            )

    def test_localized_english_is_rejected(self) -> None:
        text = REPO_TERM.replace("      ja:\n", "      en:\n")
        with self.assertRaisesRegex(GlossaryError, "canonical English"):
            self.load_text(text)

    def test_language_tags_are_unique_ignoring_case(self) -> None:
        text = REPO_TERM.replace(
            "    origin: repository\n",
            "      JA:\n"
            "        term: 別表記\n"
            "    origin: repository\n",
        )
        with self.assertRaisesRegex(GlossaryError, "duplicate language tags"):
            self.load_text(text)

    def test_duplicate_labels_within_one_locale_are_rejected(self) -> None:
        text = REPO_TERM.replace(
            "          - 提供ブランチ",
            "          - プロバイダーブランチ",
        )
        with self.assertRaisesRegex(GlossaryError, "duplicate labels"):
            self.load_text(text)

    def test_duplicate_yaml_mapping_key_is_rejected(self) -> None:
        text = REPO_TERM.replace(
            "    term: Provider branch\n",
            "    term: Provider branch\n    term: Duplicate\n",
        )
        with self.assertRaisesRegex(GlossaryError, "duplicate mapping key"):
            self.load_text(text)

    def test_non_string_yaml_mapping_key_is_rejected(self) -> None:
        text = REPO_TERM.replace(
            "    origin: repository\n",
            "    1: invalid\n    origin: repository\n",
        )
        with self.assertRaisesRegex(GlossaryError, "mapping keys must be strings"):
            self.load_text(text)

    def test_yaml_alias_is_rejected(self) -> None:
        text = """schema_version: 1
terms:
  - &term
    id: templates-one
    term: One
    origin: repository
    definition: One.
  - *term
"""
        with self.assertRaisesRegex(GlossaryError, "anchors and aliases"):
            self.load_text(text)

    def test_yaml_merge_key_is_rejected(self) -> None:
        text = REPO_TERM.replace(
            "    origin: repository\n",
            "    <<:\n      summary: merged\n    origin: repository\n",
        )
        with self.assertRaisesRegex(GlossaryError, "merge keys"):
            self.load_text(text)

    def test_custom_tag_is_rejected(self) -> None:
        text = REPO_TERM.replace(
            "term: Provider branch",
            "term: !custom Provider branch",
        )
        with self.assertRaisesRegex(GlossaryError, "custom tags"):
            self.load_text(text)

    def test_http_authority_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "absolute HTTPS URL"):
            self.load_text(
                EXTERNAL_TERM.replace(
                    "https://git-scm.com",
                    "http://git-scm.com",
                )
            )

    def test_authority_url_whitespace_is_rejected(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "must not contain whitespace"):
            self.load_text(
                EXTERNAL_TERM.replace(
                    "https://git-scm.com/docs/gitglossary",
                    "https://git-scm.com/docs/git glossary",
                )
            )

    def test_authority_url_credentials_are_rejected(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "without credentials"):
            self.load_text(
                EXTERNAL_TERM.replace(
                    "https://git-scm.com/docs/gitglossary",
                    "https://user:pass@git-scm.com/docs/gitglossary",
                )
            )

    def test_invalid_authority_kind_is_rejected(self) -> None:
        with self.assertRaisesRegex(GlossaryError, "normative, upstream, or conventional"):
            self.load_text(EXTERNAL_TERM.replace("kind: upstream", "kind: informal"))

    def test_self_referential_related_term_is_rejected(self) -> None:
        text = REPO_TERM.replace(
            "    definition: A branch that owns canonical publication content.\n",
            "    definition: A branch that owns canonical publication content.\n"
            "    related_terms:\n"
            "      - templates-provider-branch\n",
        )
        with self.assertRaisesRegex(GlossaryError, "must not reference the term itself"):
            self.load_text(text)

    def test_unknown_term_field_is_rejected(self) -> None:
        text = REPO_TERM.replace(
            "    origin: repository\n",
            "    origin: repository\n    owner: site\n",
        )
        with self.assertRaisesRegex(GlossaryError, "unsupported fields: owner"):
            self.load_text(text)


class IntegratedGlossaryTests(unittest.TestCase):
    def make_provider(
        self,
        root: Path,
        name: str,
        glossary: str,
        related: str | None = None,
    ) -> Path:
        provider = root / name
        docs = provider / "docs"
        docs.mkdir(parents=True)
        if related:
            glossary = glossary.replace(
                "    definition: A branch that owns canonical publication content.\n",
                "    definition: A branch that owns canonical publication content.\n"
                f"    related_terms:\n      - {related}\n",
            )
        (docs / "glossary.yml").write_text(glossary, encoding="utf-8")
        (docs / "publication-catalog.json").write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "documents": [
                        {
                            "id": "overview",
                            "source": "README.md",
                            "optional": False,
                            "home": True,
                        }
                    ],
                    "glossary": {"source": "docs/glossary.yml"},
                }
            ),
            encoding="utf-8",
        )
        return provider

    def set_glossary_source(self, provider: Path, source: object) -> None:
        catalog = provider / "docs" / "publication-catalog.json"
        value = json.loads(catalog.read_text(encoding="utf-8"))
        value["glossary"] = {"source": source}
        catalog.write_text(json.dumps(value), encoding="utf-8")

    def test_explicit_null_glossary_declaration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = self.make_provider(root, "site", REPO_TERM)
            catalog = provider / "docs" / "publication-catalog.json"
            value = json.loads(catalog.read_text(encoding="utf-8"))
            value["glossary"] = None
            catalog.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(GlossaryError, "must contain only source"):
                glossary_source_from_catalog(provider)

    def test_parent_traversal_glossary_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = self.make_provider(root, "site", REPO_TERM)
            self.set_glossary_source(provider, "../glossary.yml")
            with self.assertRaisesRegex(GlossaryError, "safe relative POSIX path"):
                glossary_source_from_catalog(provider)

    def test_absolute_glossary_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = self.make_provider(root, "site", REPO_TERM)
            self.set_glossary_source(provider, "/abs/glossary.yml")
            with self.assertRaisesRegex(GlossaryError, "safe relative POSIX path"):
                glossary_source_from_catalog(provider)

    def test_symlinked_glossary_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = self.make_provider(root, "site", REPO_TERM)
            link = provider / "docs" / "glossary-link.yml"
            try:
                link.symlink_to("glossary.yml")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are not supported in this environment")
            self.set_glossary_source(provider, "docs/glossary-link.yml")
            with self.assertRaisesRegex(GlossaryError, "must not traverse a symlink"):
                glossary_source_from_catalog(provider)

    def test_same_japanese_label_can_resolve_to_multiple_ids(self) -> None:
        first = (
            REPO_TERM.replace(
                "templates-provider-branch",
                "templates-policy-profile",
            )
            .replace("Provider branch", "Policy profile")
            .replace("プロバイダーブランチ", "プロファイル")
        )
        second = (
            REPO_TERM.replace(
                "templates-provider-branch",
                "templates-skill-profile",
            )
            .replace("Provider branch", "Skill profile")
            .replace("プロバイダーブランチ", "プロファイル")
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = self.make_provider(root, "policy", first)
            skill = self.make_provider(root, "skill", second)
            value = integrate_glossaries(
                {"policy": policy, "skill": skill},
                {"policy": "1" * 40, "skill": "2" * 40},
                "TakashiSasaki/templates",
            )
            self.assertEqual(len(value["terms"]), 2)

    def test_duplicate_ids_across_providers_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            one = self.make_provider(root, "one", REPO_TERM)
            two = self.make_provider(root, "two", REPO_TERM)
            with self.assertRaisesRegex(GlossaryError, "duplicate term IDs"):
                integrate_glossaries(
                    {"one": one, "two": two},
                    {"one": "1" * 40, "two": "2" * 40},
                    "TakashiSasaki/templates",
                )

    def test_unresolved_related_term_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = self.make_provider(
                root,
                "site",
                REPO_TERM,
                related="templates-missing-term",
            )
            with self.assertRaisesRegex(GlossaryError, "unresolved related terms"):
                integrate_glossaries(
                    {"site": provider},
                    {"site": "a" * 40},
                    "TakashiSasaki/templates",
                )

    def test_generator_is_deterministic_and_records_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = self.make_provider(root, "site", REPO_TERM)
            output1 = root / "one.json"
            output2 = root / "two.json"
            publication_args = [f"site={site}"]
            revision_args = ["site=" + "a" * 40]
            generate(
                publication_args,
                revision_args,
                "TakashiSasaki/templates",
                output1,
            )
            generate(
                publication_args,
                revision_args,
                "TakashiSasaki/templates",
                output2,
            )
            self.assertEqual(output1.read_bytes(), output2.read_bytes())
            value = json.loads(output1.read_text(encoding="utf-8"))
            term = value["terms"][0]
            self.assertEqual(term["provider"], "site")
            self.assertEqual(term["source_path"], "docs/glossary.yml")
            self.assertEqual(term["source_revision"], "a" * 40)

    def test_generator_script_runs_without_repository_pythonpath(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "generate_glossary.py"
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [sys.executable, str(script), "--help"],
                cwd=directory,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
