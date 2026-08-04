from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/architecture/final-readiness-audit.md"
ROADMAP = ROOT / "docs/architecture/completion-roadmap.md"
WORKFLOW = ROOT / ".github/workflows/contract-validation.yml"

VALIDATOR_COMMANDS = (
    ".venv/bin/python scripts/validate_contracts.py",
    ".venv/bin/python -m scripts.validate_contracts",
    ".venv/bin/python scripts/validate_contract_evolution.py",
    ".venv/bin/python -m scripts.validate_contract_evolution",
    ".venv/bin/python scripts/validate_implementation_evidence.py",
    ".venv/bin/python -m scripts.validate_implementation_evidence",
    ".venv/bin/python scripts/validate_release_evidence.py",
    ".venv/bin/python -m scripts.validate_release_evidence",
    ".venv/bin/python scripts/validate_release_bundle.py",
    ".venv/bin/python -m scripts.validate_release_bundle",
)

AUDIT_CRITERIA = (
    "Contract, schema, version, and responsibility closure",
    "Example ownership",
    "Validator entry-point coverage",
    "Generated-repository suite scope",
    "Provider neutrality",
    "Fixed execution boundary",
    "Unrelated-history boundary",
    "End-to-end generated-repository workflow",
    "Product-owned responsibility separation",
    "Merge gate",
)

AUDIT_EVIDENCE_PATHS = (
    "TEMPLATE.md",
    ".github/workflows/contract-validation.yml",
    "contracts/manifest.json",
    "contracts/surfaces.json",
    "contracts/routes.json",
    "contracts/ui-states.json",
    "contracts/viewports.json",
    "contracts/implementation-evidence.json",
    "contracts/release-evidence.json",
    "contracts/release-bundle.json",
    "schemas/contract-manifest.schema.json",
    "schemas/surfaces.schema.json",
    "schemas/routes.schema.json",
    "schemas/ui-states.schema.json",
    "schemas/viewports.schema.json",
    "schemas/implementation-evidence.schema.json",
    "schemas/release-evidence.schema.json",
    "schemas/release-bundle.schema.json",
    "scripts/validate_contracts.py",
    "scripts/validate_contract_evolution.py",
    "scripts/validate_implementation_evidence.py",
    "scripts/validate_release_evidence.py",
    "scripts/validate_release_bundle.py",
    "docs/migrations/contract-manifest-v1-to-v2.md",
    "docs/migrations/routes-v1-to-v2.md",
    "docs/migrations/ui-states-v1-to-v2.md",
    "docs/operationalization.md",
    "docs/architecture/responsibility-boundaries.md",
    "docs/architecture/contract-completeness.md",
    "docs/architecture/contract-evolution.md",
    "docs/architecture/implementation-evidence.md",
    "docs/architecture/release-evidence.md",
    "docs/architecture/release-bundle.md",
    "docs/architecture/generated-repository-conformance.md",
    "docs/architecture/validation-toolchain.md",
    "tests/test_generated_repository_conformance.py",
    "tests/test_generated_release_evidence_conformance.py",
    "tests/test_generated_release_evidence_production.py",
    "tests/test_generated_release_bundle_production.py",
    "tests/test_pages_deployment_boundary.py",
)


class FinalReadinessAuditTests(unittest.TestCase):
    def test_final_audit_closes_every_phase_four_criterion(self) -> None:
        audit = AUDIT.read_text(encoding="utf-8")

        self.assertIn("Repository audit status: complete", audit)
        self.assertIn("Open repository findings: 0", audit)
        for criterion in AUDIT_CRITERIA:
            with self.subTest(criterion=criterion):
                self.assertIn(f"| {criterion} |", audit)

        lowered = audit.lower()
        for marker in ("tbd", "todo"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, lowered)

    def test_audit_evidence_inventory_exists_as_regular_files(self) -> None:
        for relative_path in AUDIT_EVIDENCE_PATHS:
            path = ROOT / relative_path
            with self.subTest(path=relative_path):
                self.assertTrue(path.is_file(), f"missing audit evidence: {relative_path}")
                self.assertFalse(path.is_symlink(), f"symbolic audit evidence: {relative_path}")

    def test_ci_exercises_each_retained_validator_entry_point_once(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        for command in VALIDATOR_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(1, workflow.count(command))

        self.assertEqual(
            1,
            workflow.count(".venv/bin/python -m unittest discover -s tests -v"),
        )

    def test_completion_roadmap_records_closed_phase_four(self) -> None:
        roadmap = ROADMAP.read_text(encoding="utf-8")

        self.assertIn(
            "## Completed Phase 4: final template readiness audit",
            roadmap,
        )
        self.assertIn(
            "[final-readiness-audit.md](final-readiness-audit.md)",
            roadmap,
        )
        self.assertNotIn("## Remaining Phase 4", roadmap)
        self.assertNotIn("`policy`, `main`, or `site`", roadmap)
        self.assertIn("`skill`, `site`, or `policy`", roadmap)


if __name__ == "__main__":
    unittest.main()
