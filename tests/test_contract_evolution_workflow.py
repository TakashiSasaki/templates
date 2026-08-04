from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/contract-validation.yml"
README = ROOT / "README.md"
TOOLCHAIN_GUIDE = ROOT / "docs/architecture/validation-toolchain.md"
EVOLUTION_GUIDE = ROOT / "docs/architecture/contract-evolution.md"


class ContractEvolutionWorkflowTests(unittest.TestCase):
    def test_ci_runs_both_evolution_validator_entry_points_in_the_venv(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "run: .venv/bin/python scripts/validate_contract_evolution.py",
            workflow,
        )
        self.assertIn(
            "run: .venv/bin/python -m scripts.validate_contract_evolution",
            workflow,
        )
        self.assertNotIn(
            "run: python scripts/validate_contract_evolution.py", workflow
        )
        self.assertNotIn(
            "run: python -m scripts.validate_contract_evolution", workflow
        )

    def test_local_guidance_documents_all_four_validator_entry_points(self) -> None:
        commands = (
            "python scripts/validate_contracts.py",
            "python -m scripts.validate_contracts",
            "python scripts/validate_contract_evolution.py",
            "python -m scripts.validate_contract_evolution",
        )

        for source_path in (README, TOOLCHAIN_GUIDE):
            source = source_path.read_text(encoding="utf-8")
            with self.subTest(source=source_path.name):
                for command in commands:
                    self.assertIn(command, source)

    def test_evolution_guide_defines_review_boundary(self) -> None:
        guide = EVOLUTION_GUIDE.read_text(encoding="utf-8")

        self.assertIn("## Change classification", guide)
        self.assertIn("## Stable identifiers", guide)
        self.assertIn("## Synchronized change set", guide)
        self.assertIn("cannot prove that maintainers selected the correct semantic classification", guide)


if __name__ == "__main__":
    unittest.main()
