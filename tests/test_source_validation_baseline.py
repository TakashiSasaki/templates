from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "contract-validation.yml"
README = ROOT / "README.md"
POLICY = ROOT / "policy" / "repository" / "maintainer-validation.md"

SOURCE_VALIDATOR_COMMANDS = (
    "python scripts/validate_distribution.py",
    "python -m scripts.validate_distribution",
    "python scripts/validate_publication_catalog.py",
    "python -m scripts.validate_publication_catalog",
    "python scripts/validate_translations.py",
    "python -m scripts.validate_translations",
)

WORKFLOW_COMMANDS = (
    "run: .venv/bin/python scripts/validate_distribution.py",
    "run: .venv/bin/python -m scripts.validate_distribution",
    "run: .venv/bin/python scripts/validate_publication_catalog.py",
    "run: .venv/bin/python -m scripts.validate_publication_catalog",
    "run: .venv/bin/python scripts/validate_translations.py",
    "run: .venv/bin/python -m scripts.validate_translations",
)


class SourceValidationBaselineTests(unittest.TestCase):
    def test_readme_documents_every_source_validator_form(self) -> None:
        text = README.read_text(encoding="utf-8")
        for command in SOURCE_VALIDATOR_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(1, text.count(command))

    def test_repository_policy_requires_every_source_validator_form(self) -> None:
        text = POLICY.read_text(encoding="utf-8")
        for command in SOURCE_VALIDATOR_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(1, text.count(command))

    def test_ci_runs_every_source_validator_form_exactly_once(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for command in WORKFLOW_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(1, text.count(command))


if __name__ == "__main__":
    unittest.main()
