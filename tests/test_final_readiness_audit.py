from __future__ import annotations

import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SOURCE_ROOT / "template"
AUDIT = SOURCE_ROOT / "docs/architecture/final-readiness-audit.md"
ROADMAP = SOURCE_ROOT / "docs/architecture/completion-roadmap.md"
TOOLCHAIN = TEMPLATE_ROOT / "docs/architecture/validation-toolchain.md"
WORKFLOW = SOURCE_ROOT / ".github/workflows/contract-validation.yml"

CANONICAL_VALIDATOR_COMMANDS = (
    "run: ../.venv/bin/python scripts/validate_contracts.py",
    "run: ../.venv/bin/python -m scripts.validate_contracts",
    "run: ../.venv/bin/python scripts/validate_contract_evolution.py",
    "run: ../.venv/bin/python -m scripts.validate_contract_evolution",
    "run: ../.venv/bin/python scripts/validate_implementation_evidence.py",
    "run: ../.venv/bin/python -m scripts.validate_implementation_evidence",
    "run: ../.venv/bin/python scripts/validate_release_evidence.py",
    "run: ../.venv/bin/python -m scripts.validate_release_evidence",
    "run: ../.venv/bin/python scripts/validate_release_bundle.py",
    "run: ../.venv/bin/python -m scripts.validate_release_bundle",
)

TOOLCHAIN_VALIDATOR_COMMANDS = tuple(
    command.removeprefix("run: ../.venv/bin/") for command in CANONICAL_VALIDATOR_COMMANDS
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

SOURCE_AUDIT_EVIDENCE_PATHS = (
    ".github/workflows/contract-validation.yml",
    "distribution-manifest.json",
    "scripts/validate_distribution.py",
    "docs/architecture/distribution-boundary.md",
    "docs/architecture/generated-repository-conformance.md",
    "tests/test_generated_repository_conformance.py",
    "tests/test_generated_release_evidence_conformance.py",
    "tests/test_generated_release_evidence_production.py",
    "tests/test_generated_release_bundle_production.py",
    "tests/test_pages_deployment_boundary.py",
)

TEMPLATE_AUDIT_EVIDENCE_PATHS = (
    "TEMPLATE.md",
    "README.md",
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
    "docs/architecture/validation-toolchain.md",
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
        for root, paths in (
            (SOURCE_ROOT, SOURCE_AUDIT_EVIDENCE_PATHS),
            (TEMPLATE_ROOT, TEMPLATE_AUDIT_EVIDENCE_PATHS),
        ):
            for relative_path in paths:
                path = root / relative_path
                with self.subTest(root=root.name, path=relative_path):
                    self.assertTrue(path.is_file(), f"missing audit evidence: {path}")
                    self.assertFalse(path.is_symlink(), f"symbolic audit evidence: {path}")

    def test_ci_exercises_each_canonical_validator_entry_point_once(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        for command in CANONICAL_VALIDATOR_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(1, workflow.count(command))

        for legacy_prefix in (
            "run: .venv/bin/python scripts/validate_contracts.py",
            "run: .venv/bin/python -m scripts.validate_contracts",
            "run: .venv/bin/python scripts/validate_contract_evolution.py",
            "run: .venv/bin/python -m scripts.validate_contract_evolution",
            "run: .venv/bin/python scripts/validate_implementation_evidence.py",
            "run: .venv/bin/python -m scripts.validate_implementation_evidence",
            "run: .venv/bin/python scripts/validate_release_evidence.py",
            "run: .venv/bin/python -m scripts.validate_release_evidence",
            "run: .venv/bin/python scripts/validate_release_bundle.py",
            "run: .venv/bin/python -m scripts.validate_release_bundle",
        ):
            with self.subTest(legacy_prefix=legacy_prefix):
                self.assertNotIn(legacy_prefix, workflow)

        self.assertEqual(
            1,
            workflow.count(
                "run: .venv/bin/python -m unittest discover -s tests -v"
            ),
        )
        self.assertEqual(
            1,
            workflow.count(
                "run: ../.venv/bin/python -m unittest discover -s tests -v"
            ),
        )
        self.assertEqual(
            1,
            workflow.count("run: .venv/bin/python scripts/validate_distribution.py"),
        )
        self.assertEqual(
            1,
            workflow.count("run: .venv/bin/python -m scripts.validate_distribution"),
        )

    def test_validation_toolchain_documents_all_retained_validator_forms(self) -> None:
        toolchain = TOOLCHAIN.read_text(encoding="utf-8")
        local_commands = toolchain.split(
            "Run all supported validator forms and the tests:", 1
        )[1].split("For product-mode release evidence", 1)[0]

        self.assertIn("all ten validator forms", toolchain)
        self.assertNotIn("all eight validator forms", toolchain)
        for command in TOOLCHAIN_VALIDATOR_COMMANDS:
            with self.subTest(command=command):
                self.assertIn(command, local_commands)

        product_boundary = toolchain.split("## Product-repository boundary", 1)[1]
        self.assertIn(
            "release-bundle artifact coverage and handoff binding",
            product_boundary,
        )

    def test_completion_roadmap_records_closed_phase_four(self) -> None:
        roadmap = ROADMAP.read_text(encoding="utf-8")

        self.assertIn(
            "## Completed Phase 4: final template readiness audit",
            roadmap,
        )
        self.assertIn("(final-readiness-audit.md)", roadmap)
        self.assertNotIn("## Remaining Phase 4", roadmap)
        self.assertNotIn("`policy`, `main`, or `site`", roadmap)
        for branch in ("skill", "site", "policy"):
            with self.subTest(branch=branch):
                self.assertIn(f"`{branch}`", roadmap)


if __name__ == "__main__":
    unittest.main()
