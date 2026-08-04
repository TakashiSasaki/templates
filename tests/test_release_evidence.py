from __future__ import annotations

import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import validate_contracts  # noqa: E402
from scripts import validate_release_evidence  # noqa: E402

REVISION = "0123456789abcdef0123456789abcdef01234567"


class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = validate_contracts.load_contract_manifest(ROOT)
        self.documents = validate_contracts.load_contract_documents(ROOT)
        self.release = self.documents["release_evidence"]

    def product_documents(self) -> dict[str, object]:
        documents = copy.deepcopy(self.documents)
        implementation = documents["implementation_evidence"]
        implementation["mode"] = "product"
        implementation["commands"] = [
            {
                "id": "product-evidence",
                "command": "product-test --implementation-evidence",
                "purpose": "Run all product implementation evidence.",
            }
        ]
        implementation["releaseGates"] = [
            {
                "id": "implementation-release",
                "purpose": "Block release unless all implementation evidence passes.",
                "commandIds": ["product-evidence"],
            }
        ]
        for record in implementation["records"]:
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
                        "expectedResult": "The declared behavior is observed.",
                    }
                )

        command = implementation["commands"][0]["command"]
        release = documents["release_evidence"]
        release.update(
            {
                "mode": "product",
                "subject": {
                    "revision": REVISION,
                    "description": "Exact Git revision approved for release.",
                },
                "provenance": {
                    "kind": "ci-run",
                    "id": "run-123",
                    "locator": "ci/runs/123",
                    "generatedAt": "2026-08-04T00:03:00Z",
                },
                "decision": {
                    "status": "approved",
                    "decidedAt": "2026-08-04T00:02:00Z",
                    "description": "All selected release gates passed.",
                },
                "commandResults": [
                    {
                        "commandId": "product-evidence",
                        "commandDigest": hashlib.sha256(
                            command.encode("utf-8")
                        ).hexdigest(),
                        "status": "passed",
                        "exitCode": 0,
                        "startedAt": "2026-08-04T00:00:00Z",
                        "completedAt": "2026-08-04T00:01:00Z",
                        "resultLocator": "ci/runs/123#product-evidence",
                    }
                ],
                "gateResults": [
                    {
                        "gateId": "implementation-release",
                        "status": "passed",
                        "resultLocator": "ci/runs/123#implementation-release",
                    }
                ],
            }
        )
        return documents

    def validate_product(
        self,
        documents: dict[str, object],
        *,
        expected_revision: str | None = REVISION,
    ) -> list[str]:
        return validate_release_evidence.validate_release_evidence_documents(
            self.manifest,
            documents,
            expected_revision=expected_revision,
        )

    def test_manifest_registers_initial_release_evidence_family(self) -> None:
        entry = next(
            entry
            for entry in self.manifest["contracts"]
            if entry["id"] == "release_evidence"
        )

        self.assertEqual("contracts/release-evidence.json", entry["document"])
        self.assertEqual(
            "schemas/release-evidence.schema.json",
            entry["schema"],
        )
        self.assertEqual("release-evidence", entry["migrationSlug"])
        self.assertEqual(1, entry["documentSchemaVersion"])
        self.assertEqual(
            [{"version": 1, "changeType": "initial"}],
            entry["versionHistory"],
        )

    def test_repository_template_document_is_structurally_and_semantically_valid(self) -> None:
        schema = validate_contracts.load_json(
            ROOT / "schemas/release-evidence.schema.json"
        )

        self.assertTrue(Draft202012Validator(schema).is_valid(self.release))
        self.assertEqual(
            [],
            validate_release_evidence.validate_release_evidence_documents(
                self.manifest,
                self.documents,
            ),
        )

    def test_fully_bound_product_release_is_valid(self) -> None:
        documents = self.product_documents()

        self.assertEqual([], self.validate_product(documents))

    def test_template_release_requires_template_implementation_evidence(self) -> None:
        documents = self.product_documents()
        documents["release_evidence"] = copy.deepcopy(self.release)

        errors = self.validate_product(documents, expected_revision=None)

        self.assertIn(
            "release evidence: template mode requires template implementation evidence",
            errors,
        )

    def test_template_release_rejects_an_expected_revision(self) -> None:
        errors = validate_release_evidence.validate_release_evidence_documents(
            self.manifest,
            self.documents,
            expected_revision=REVISION,
        )

        self.assertIn(
            "release evidence: template mode must not receive an expected revision",
            errors,
        )

    def test_product_release_requires_product_implementation_evidence(self) -> None:
        documents = self.product_documents()
        documents["implementation_evidence"]["mode"] = "template"

        errors = self.validate_product(documents)

        self.assertIn(
            "release evidence: product mode requires product implementation evidence",
            errors,
        )

    def test_product_release_requires_expected_revision(self) -> None:
        documents = self.product_documents()

        errors = self.validate_product(documents, expected_revision=None)

        self.assertIn(
            "release evidence: product mode requires an expected revision",
            errors,
        )

    def test_product_release_rejects_revision_mismatch(self) -> None:
        documents = self.product_documents()

        errors = self.validate_product(
            documents,
            expected_revision="f" * 40,
        )

        self.assertIn(
            "release evidence subject: "
            f"revision {REVISION!r} does not match expected revision {('f' * 40)!r}",
            errors,
        )

    def test_missing_and_unknown_gate_results_are_rejected(self) -> None:
        documents = self.product_documents()
        documents["release_evidence"]["gateResults"][0]["gateId"] = "unknown-gate"

        errors = self.validate_product(documents)

        self.assertIn(
            "missing release evidence gate result: implementation-release",
            errors,
        )
        self.assertIn(
            "unknown release evidence gate result: unknown-gate",
            errors,
        )

    def test_missing_and_unknown_command_results_are_rejected(self) -> None:
        documents = self.product_documents()
        documents["release_evidence"]["commandResults"][0][
            "commandId"
        ] = "unknown-command"

        errors = self.validate_product(documents)

        self.assertIn(
            "missing release evidence command result: product-evidence",
            errors,
        )
        self.assertIn(
            "unknown release evidence command result: unknown-command",
            errors,
        )

    def test_duplicate_gate_and_command_results_are_rejected(self) -> None:
        documents = self.product_documents()
        release = documents["release_evidence"]
        release["gateResults"].append(copy.deepcopy(release["gateResults"][0]))
        release["commandResults"].append(
            copy.deepcopy(release["commandResults"][0])
        )

        errors = self.validate_product(documents)

        self.assertIn(
            "duplicate release evidence gate result: implementation-release",
            errors,
        )
        self.assertIn(
            "duplicate release evidence command result: product-evidence",
            errors,
        )

    def test_command_digest_binds_the_authoritative_command(self) -> None:
        documents = self.product_documents()
        documents["release_evidence"]["commandResults"][0][
            "commandDigest"
        ] = "0" * 64

        errors = self.validate_product(documents)

        self.assertIn(
            "release evidence command result product-evidence: "
            "commandDigest does not match the authoritative command",
            errors,
        )

    def test_non_utf8_command_text_is_rejected_without_crashing(self) -> None:
        documents = self.product_documents()
        documents["implementation_evidence"]["commands"][0][
            "command"
        ] = "echo ok\ud800"

        errors = self.validate_product(documents)

        self.assertIn(
            "release evidence command product-evidence: "
            "authoritative command must be UTF-8 encodable",
            errors,
        )

    def test_failed_command_gate_and_decision_block_release(self) -> None:
        documents = self.product_documents()
        release = documents["release_evidence"]
        release["commandResults"][0]["status"] = "failed"
        release["commandResults"][0]["exitCode"] = 1
        release["gateResults"][0]["status"] = "failed"
        release["decision"]["status"] = "rejected"

        errors = self.validate_product(documents)

        self.assertIn(
            "release evidence command result product-evidence: status must be passed",
            errors,
        )
        self.assertIn(
            "release evidence command result product-evidence: exitCode must be 0",
            errors,
        )
        self.assertIn(
            "release evidence gate result implementation-release: status must be passed",
            errors,
        )
        self.assertIn(
            "release evidence decision: release status must be approved",
            errors,
        )

    def test_gate_cannot_pass_when_its_command_did_not_pass(self) -> None:
        documents = self.product_documents()
        documents["release_evidence"]["commandResults"][0]["status"] = "failed"

        errors = self.validate_product(documents)

        self.assertIn(
            "release evidence gate result implementation-release: "
            "command product-evidence did not pass",
            errors,
        )

    def test_command_completion_must_not_precede_start(self) -> None:
        documents = self.product_documents()
        result = documents["release_evidence"]["commandResults"][0]
        result["completedAt"] = "2026-08-03T23:59:00Z"

        errors = self.validate_product(documents)

        self.assertIn(
            "release evidence command result product-evidence: "
            "completedAt must not precede startedAt",
            errors,
        )

    def test_nanosecond_command_order_is_preserved(self) -> None:
        documents = self.product_documents()
        result = documents["release_evidence"]["commandResults"][0]
        result["startedAt"] = "2026-08-04T00:00:00.000000001Z"
        result["completedAt"] = "2026-08-04T00:00:00.000000000Z"

        errors = self.validate_product(documents)

        self.assertIn(
            "release evidence command result product-evidence: "
            "completedAt must not precede startedAt",
            errors,
        )

    def test_nanosecond_decision_order_is_preserved(self) -> None:
        documents = self.product_documents()
        release = documents["release_evidence"]
        release["commandResults"][0][
            "completedAt"
        ] = "2026-08-04T00:01:00.000000001Z"
        release["decision"]["decidedAt"] = "2026-08-04T00:01:00.000000000Z"

        errors = self.validate_product(documents)

        self.assertIn(
            "release evidence decision: "
            "decidedAt must not precede command completion",
            errors,
        )

    def test_nanosecond_generation_order_is_preserved(self) -> None:
        documents = self.product_documents()
        release = documents["release_evidence"]
        release["decision"]["decidedAt"] = "2026-08-04T00:02:00.000000001Z"
        release["provenance"][
            "generatedAt"
        ] = "2026-08-04T00:02:00.000000000Z"

        errors = self.validate_product(documents)

        self.assertIn(
            "release evidence provenance: "
            "generatedAt must not precede decidedAt",
            errors,
        )

    def test_decision_and_generation_follow_command_completion(self) -> None:
        documents = self.product_documents()
        release = documents["release_evidence"]
        release["decision"]["decidedAt"] = "2026-08-04T00:00:30Z"
        release["provenance"]["generatedAt"] = "2026-08-04T00:00:00Z"

        errors = self.validate_product(documents)

        self.assertIn(
            "release evidence decision: "
            "decidedAt must not precede command completion",
            errors,
        )
        self.assertIn(
            "release evidence provenance: "
            "generatedAt must not precede decidedAt",
            errors,
        )

    def test_template_mode_cannot_claim_product_release_results(self) -> None:
        documents = self.product_documents()
        documents["release_evidence"]["mode"] = "template"

        errors = self.validate_product(documents)

        self.assertIn(
            "release evidence: template mode must not claim subject",
            errors,
        )
        self.assertIn(
            "release evidence: template mode requires commandResults to be empty",
            errors,
        )
        self.assertIn(
            "release evidence: template mode requires gateResults to be empty",
            errors,
        )

    def test_repository_root_symlink_is_rejected_before_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            alias = Path(temporary_directory) / "repository-link"
            alias.symlink_to(root.name, target_is_directory=True)

            errors = validate_release_evidence.validate_release_evidence(alias)

        self.assertEqual(
            ["repository root must not be a symbolic link"],
            errors,
        )

    def test_ci_runs_both_release_evidence_entry_points(self) -> None:
        workflow = (
            ROOT / ".github/workflows/contract-validation.yml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "run: .venv/bin/python scripts/validate_release_evidence.py",
            workflow,
        )
        self.assertIn(
            "run: .venv/bin/python -m scripts.validate_release_evidence",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
