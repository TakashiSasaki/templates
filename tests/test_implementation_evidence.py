from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

SOURCE_ROOT = Path(__file__).resolve().parents[1]
ROOT = SOURCE_ROOT / "template"
sys.path.insert(0, str(SOURCE_ROOT))

from scripts import validate_contracts  # noqa: E402
from scripts import validate_implementation_evidence  # noqa: E402


class ImplementationEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = validate_contracts.load_contract_manifest(ROOT)
        self.documents = validate_contracts.load_contract_documents(ROOT)
        self.evidence = self.documents["implementation_evidence"]

    def verified_product_documents(self) -> dict[str, object]:
        documents = copy.deepcopy(self.documents)
        evidence = documents["implementation_evidence"]
        evidence["mode"] = "product"
        evidence["commands"] = [
            {
                "id": "product-evidence",
                "command": "product-test --implementation-evidence",
                "purpose": "Run all product implementation evidence.",
            }
        ]
        evidence["releaseGates"] = [
            {
                "id": "implementation-release",
                "purpose": "Block release unless all implementation evidence passes.",
                "commandIds": ["product-evidence"],
            }
        ]
        for record in evidence["records"]:
            record["implementationBoundary"] = {
                "status": "verified",
                "description": record["implementationBoundary"]["description"],
                "locator": f"src/{record['id']}",
            }
            record["releaseGateIds"] = ["implementation-release"]
            for proof in record["positiveEvidence"] + record["negativeEvidence"]:
                proof.update(
                    {
                        "status": "verified",
                        "kind": "integration-test",
                        "locator": f"tests/{proof['id']}.test",
                        "commandId": "product-evidence",
                        "expectedResult": "The declared behavior is observed and the command exits successfully.",
                    }
                )
        return documents

    def test_manifest_registers_initial_contract_family(self) -> None:
        entry = next(
            entry
            for entry in self.manifest["contracts"]
            if entry["id"] == "implementation_evidence"
        )

        self.assertEqual(
            "contracts/implementation-evidence.json", entry["document"]
        )
        self.assertEqual(
            "schemas/implementation-evidence.schema.json", entry["schema"]
        )
        self.assertEqual("implementation-evidence", entry["migrationSlug"])
        self.assertEqual(1, entry["documentSchemaVersion"])
        self.assertEqual(
            [{"version": 1, "changeType": "initial"}],
            entry["versionHistory"],
        )

    def test_repository_template_document_is_structurally_and_semantically_valid(self) -> None:
        schema = validate_contracts.load_json(
            ROOT / "schemas/implementation-evidence.schema.json"
        )

        self.assertTrue(Draft202012Validator(schema).is_valid(self.evidence))
        self.assertEqual(
            [],
            validate_implementation_evidence.validate_evidence_documents(
                self.manifest, self.documents
            ),
        )

    def test_missing_target_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        evidence = documents["implementation_evidence"]
        evidence["records"] = [
            record
            for record in evidence["records"]
            if record["target"] != {"kind": "surface", "id": "public"}
        ]

        errors = validate_implementation_evidence.validate_evidence_documents(
            self.manifest, documents
        )

        self.assertIn("missing implementation evidence target: surface public", errors)

    def test_unknown_target_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        evidence = documents["implementation_evidence"]
        evidence["records"][0]["target"] = {
            "kind": "surface",
            "id": "unknown",
        }

        errors = validate_implementation_evidence.validate_evidence_documents(
            self.manifest, documents
        )

        self.assertIn("unknown implementation evidence target: surface unknown", errors)

    def test_duplicate_target_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        evidence = documents["implementation_evidence"]
        evidence["records"][1]["target"] = copy.deepcopy(
            evidence["records"][0]["target"]
        )

        errors = validate_implementation_evidence.validate_evidence_documents(
            self.manifest, documents
        )

        self.assertTrue(
            any(error.startswith("duplicate implementation evidence target:") for error in errors),
            errors,
        )

    def test_fully_verified_product_mode_is_valid(self) -> None:
        documents = self.verified_product_documents()

        errors = validate_implementation_evidence.validate_evidence_documents(
            self.manifest, documents
        )

        self.assertEqual([], errors)

    def test_product_mode_rejects_unverified_boundary_and_proof(self) -> None:
        documents = self.verified_product_documents()
        record = documents["implementation_evidence"]["records"][0]
        record["implementationBoundary"]["status"] = "required"
        record["positiveEvidence"][0]["status"] = "required"

        errors = validate_implementation_evidence.validate_evidence_documents(
            self.manifest, documents
        )

        self.assertTrue(
            any("requires a verified implementation boundary" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("product mode requires status verified" in error for error in errors),
            errors,
        )

    def test_protected_route_requires_negative_evidence(self) -> None:
        documents = self.verified_product_documents()
        evidence = documents["implementation_evidence"]
        record = next(
            record
            for record in evidence["records"]
            if record["target"]
            == {"kind": "route", "id": "application-home"}
        )
        record["negativeEvidence"] = []

        errors = validate_implementation_evidence.validate_evidence_documents(
            self.manifest, documents
        )

        self.assertTrue(
            any("route application-home requires negative evidence" in error for error in errors),
            errors,
        )

    def test_selected_release_gate_must_execute_evidence_command(self) -> None:
        documents = self.verified_product_documents()
        evidence = documents["implementation_evidence"]
        evidence["commands"].append(
            {
                "id": "detached-command",
                "command": "product-test --detached",
                "purpose": "Exercise one detached proof.",
            }
        )
        proof = evidence["records"][0]["positiveEvidence"][0]
        proof["commandId"] = "detached-command"

        errors = validate_implementation_evidence.validate_evidence_documents(
            self.manifest, documents
        )

        self.assertTrue(
            any(
                "evidence command detached-command is not executed by a selected release gate"
                in error
                for error in errors
            ),
            errors,
        )

    def test_registered_transition_requires_evidence_target(self) -> None:
        documents = copy.deepcopy(self.documents)
        evidence = documents["implementation_evidence"]
        evidence["records"] = [
            record
            for record in evidence["records"]
            if record["target"]
            != {
                "kind": "contract-transition",
                "contractId": "routes",
                "fromVersion": 1,
                "toVersion": 2,
            }
        ]

        errors = validate_implementation_evidence.validate_evidence_documents(
            self.manifest, documents
        )

        self.assertIn(
            "missing implementation evidence target: routes version 1 to 2",
            errors,
        )

    def test_template_mode_cannot_claim_product_commands_or_release_gates(self) -> None:
        documents = copy.deepcopy(self.documents)
        evidence = documents["implementation_evidence"]
        evidence["commands"] = [
            {
                "id": "claimed-command",
                "command": "false",
                "purpose": "Invalid template claim.",
            }
        ]
        evidence["releaseGates"] = [
            {
                "id": "claimed-gate",
                "purpose": "Invalid template gate.",
                "commandIds": ["claimed-command"],
            }
        ]

        errors = validate_implementation_evidence.validate_evidence_documents(
            self.manifest, documents
        )

        self.assertIn(
            "implementation evidence: template mode requires commands to be empty",
            errors,
        )
        self.assertIn(
            "implementation evidence: template mode requires releaseGates to be empty",
            errors,
        )

    def test_repository_root_symlink_is_rejected_before_loading(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            alias = Path(temporary_directory) / "repository-link"
            alias.symlink_to(root.name, target_is_directory=True)

            errors = (
                validate_implementation_evidence.validate_implementation_evidence(
                    alias
                )
            )

        self.assertEqual(
            ["repository root must not be a symbolic link"],
            errors,
        )

    def test_repository_root_ancestor_symlink_is_rejected_before_loading(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            real_parent = temporary / "real-parent"
            real_parent.mkdir()
            root = real_parent / "repository"
            root.mkdir()
            alias_parent = temporary / "alias-parent"
            alias_parent.symlink_to(real_parent, target_is_directory=True)
            alias = alias_parent / root.name

            errors = (
                validate_implementation_evidence.validate_implementation_evidence(
                    alias
                )
            )

        self.assertEqual(
            ["repository root path must not contain symbolic links"],
            errors,
        )

    def test_ci_runs_both_implementation_evidence_entry_points(self) -> None:
        workflow = (
            SOURCE_ROOT / ".github/workflows/contract-validation.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("working-directory: template", workflow)
        self.assertIn(
            "run: ../.venv/bin/python scripts/validate_implementation_evidence.py",
            workflow,
        )
        self.assertIn(
            "run: ../.venv/bin/python -m scripts.validate_implementation_evidence",
            workflow,
        )
        self.assertNotIn(
            "run: .venv/bin/python scripts/validate_implementation_evidence.py",
            workflow,
        )
        self.assertNotIn(
            "run: .venv/bin/python -m scripts.validate_implementation_evidence",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
