from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import validate_contracts  # noqa: E402
from scripts import validate_release_bundle  # noqa: E402

REVISION = "0123456789abcdef0123456789abcdef01234567"


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


class ReleaseBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = validate_contracts.load_contract_manifest(ROOT)
        self.documents = validate_contracts.load_contract_documents(ROOT)
        self.bundle = self.documents["release_bundle"]
        self.schema = validate_contracts.load_json(
            ROOT / "schemas/release-bundle.schema.json"
        )

    def product_documents(self) -> tuple[dict[str, object], dict[str, str]]:
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

        entries = [
            entry
            for entry in self.manifest["contracts"]
            if entry["id"] != "release_bundle"
        ]
        digests = {entry["id"]: _digest(entry["id"]) for entry in entries}
        bundle = documents["release_bundle"]
        bundle.update(
            {
                "mode": "product",
                "subject": {
                    "revision": REVISION,
                    "description": "Candidate revision represented by this bundle.",
                },
                "provenance": {
                    "kind": "ci-run",
                    "id": "bundle-run-123",
                    "locator": "ci/runs/123#release-bundle",
                    "generatedAt": "2026-08-04T00:04:00Z",
                },
                "handoff": {
                    "status": "ready",
                    "description": "The immutable evidence set is ready for handoff.",
                },
                "artifacts": [
                    {
                        "contractId": entry["id"],
                        "path": entry["document"],
                        "sha256": digests[entry["id"]],
                    }
                    for entry in entries
                ],
            }
        )
        return documents, digests

    def validate_product(
        self,
        documents: dict[str, object],
        digests: dict[str, str],
        *,
        expected_revision: str | None = REVISION,
    ) -> list[str]:
        return validate_release_bundle.validate_release_bundle_documents(
            self.manifest,
            documents,
            artifact_digests=digests,
            expected_revision=expected_revision,
        )

    def test_manifest_registers_initial_release_bundle_family(self) -> None:
        entry = next(
            entry
            for entry in self.manifest["contracts"]
            if entry["id"] == "release_bundle"
        )

        self.assertEqual("contracts/release-bundle.json", entry["document"])
        self.assertEqual("schemas/release-bundle.schema.json", entry["schema"])
        self.assertEqual("release-bundle", entry["migrationSlug"])
        self.assertEqual(1, entry["documentSchemaVersion"])
        self.assertEqual(
            [{"version": 1, "changeType": "initial"}],
            entry["versionHistory"],
        )

    def test_repository_template_document_is_structurally_and_semantically_valid(self) -> None:
        self.assertTrue(Draft202012Validator(self.schema).is_valid(self.bundle))
        self.assertEqual(
            [],
            validate_release_bundle.validate_release_bundle_documents(
                self.manifest,
                self.documents,
                artifact_digests={},
            ),
        )

    def test_fully_bound_product_bundle_is_valid(self) -> None:
        documents, digests = self.product_documents()
        bundle = documents["release_bundle"]

        self.assertTrue(
            Draft202012Validator(self.schema).is_valid(bundle),
            list(Draft202012Validator(self.schema).iter_errors(bundle)),
        )
        self.assertEqual([], self.validate_product(documents, digests))

    def test_product_bundle_requires_expected_revision(self) -> None:
        documents, digests = self.product_documents()

        errors = self.validate_product(
            documents,
            digests,
            expected_revision=None,
        )

        self.assertIn(
            "release bundle: product mode requires an expected revision",
            errors,
        )

    def test_bundle_revision_must_match_expected_and_release_revision(self) -> None:
        documents, digests = self.product_documents()
        documents["release_bundle"]["subject"]["revision"] = "f" * 40

        errors = self.validate_product(documents, digests)

        self.assertIn(
            "release bundle subject: revision does not match expected revision",
            errors,
        )
        self.assertIn(
            "release bundle subject: revision does not match release evidence",
            errors,
        )

    def test_bundle_requires_exact_active_contract_coverage(self) -> None:
        documents, digests = self.product_documents()
        artifacts = documents["release_bundle"]["artifacts"]
        missing = artifacts.pop(0)["contractId"]
        artifacts.append(
            {
                "contractId": "unknown-contract",
                "path": "contracts/unknown.json",
                "sha256": "0" * 64,
            }
        )

        errors = self.validate_product(documents, digests)

        self.assertIn(f"missing release bundle artifact: {missing}", errors)
        self.assertIn(
            "unknown release bundle artifact: unknown-contract",
            errors,
        )

    def test_bundle_manifest_must_not_digest_itself(self) -> None:
        documents, digests = self.product_documents()
        documents["release_bundle"]["artifacts"].append(
            {
                "contractId": "release_bundle",
                "path": "contracts/release-bundle.json",
                "sha256": "0" * 64,
            }
        )

        errors = self.validate_product(documents, digests)

        self.assertIn(
            "release bundle must not include its own contract document",
            errors,
        )

    def test_artifact_path_and_digest_are_bound_to_current_contract(self) -> None:
        documents, digests = self.product_documents()
        artifact = documents["release_bundle"]["artifacts"][0]
        contract_id = artifact["contractId"]
        artifact["path"] = "contracts/other.json"
        artifact["sha256"] = "0" * 64

        errors = self.validate_product(documents, digests)

        self.assertIn(
            f"release bundle artifact {contract_id}: path does not match manifest",
            errors,
        )
        self.assertIn(
            f"release bundle artifact {contract_id}: sha256 does not match current bytes",
            errors,
        )

    def test_artifact_order_and_identity_must_be_deterministic(self) -> None:
        documents, digests = self.product_documents()
        artifacts = documents["release_bundle"]["artifacts"]
        artifacts[0], artifacts[1] = artifacts[1], artifacts[0]
        artifacts.append(copy.deepcopy(artifacts[0]))

        errors = self.validate_product(documents, digests)

        self.assertIn(
            "release bundle artifacts must follow manifest contract order",
            errors,
        )
        self.assertIn(
            f"duplicate release bundle artifact: {artifacts[0]['contractId']}",
            errors,
        )

    def test_bundle_generation_must_follow_release_evidence(self) -> None:
        documents, digests = self.product_documents()
        documents["release_bundle"]["provenance"][
            "generatedAt"
        ] = "2026-08-04T00:02:59.999999999Z"

        errors = self.validate_product(documents, digests)

        self.assertIn(
            "release bundle provenance: generatedAt must not precede release evidence generation",
            errors,
        )

    def test_template_mode_cannot_claim_product_handoff(self) -> None:
        documents, digests = self.product_documents()
        documents["release_bundle"]["mode"] = "template"

        errors = self.validate_product(documents, digests)

        self.assertIn(
            "release bundle: template mode must not claim subject",
            errors,
        )
        self.assertIn(
            "release bundle: template mode requires artifacts to be empty",
            errors,
        )

    def test_ci_runs_both_release_bundle_entry_points(self) -> None:
        workflow = (
            ROOT / ".github/workflows/contract-validation.yml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "run: .venv/bin/python scripts/validate_release_bundle.py",
            workflow,
        )
        self.assertIn(
            "run: .venv/bin/python -m scripts.validate_release_bundle",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
