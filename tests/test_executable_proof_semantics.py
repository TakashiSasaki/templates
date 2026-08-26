from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_COMPONENT = ROOT / "components" / "lifecycle.implementation-evidence" / "files"
IMPLEMENTATION_SCHEMA = IMPLEMENTATION_COMPONENT / "schemas" / "implementation-evidence.schema.json"
IMPLEMENTATION_VALIDATOR = IMPLEMENTATION_COMPONENT / ".template-composition" / "validators" / "validate_implementation_evidence.py"
CONTRACT_COMMON = ROOT / "components" / "lifecycle.contract-evolution" / "files" / ".template-composition" / "validators"
WEBAPP_SCRIPTS = ROOT / "components" / "artifact.webapp-core" / "files" / "scripts"
RELEASE_EXECUTION_VALIDATOR = ROOT / "components" / "lifecycle.release-execution" / "files" / ".template-composition" / "validators" / "validate_release_execution.py"

for path in (CONTRACT_COMMON, WEBAPP_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


implementation = load_module("executable_proof_implementation", IMPLEMENTATION_VALIDATOR)
webapp = load_module("executable_proof_webapp", WEBAPP_SCRIPTS / "validate_webapp_evidence.py")
release_execution = load_module("executable_proof_release_execution", RELEASE_EXECUTION_VALIDATOR)


def product_evidence(
    *,
    proof_kind: str = "end-to-end-test",
    capabilities: list[str] | None = None,
    supports_negative: bool = True,
) -> dict:
    return {
        "$schema": "../schemas/implementation-evidence.schema.json",
        "schemaVersion": 6,
        "mode": "product",
        "commands": [
            {
                "id": "product-proof",
                "command": "python tests/proof.py",
                "purpose": "Execute the product proof harness.",
                "execution": {
                    "capabilities": capabilities or ["end-to-end"],
                    "harness": {
                        "kind": "repository-file",
                        "locator": "tests/proof.py",
                        "invocation": "python-script",
                    },
                    "supportsNegativePath": supports_negative,
                },
            }
        ],
        "releaseGates": [
            {
                "id": "product-release",
                "purpose": "Require the product proof.",
                "commandIds": ["product-proof"],
            }
        ],
        "requirements": [
            {
                "id": "REQ-PRODUCT-PROOF",
                "description": "The declared surface has executable product proof.",
                "recordIds": ["surface-proof"],
                "requiredPositiveProofKinds": [proof_kind],
            }
        ],
        "records": [
            {
                "id": "surface-proof",
                "target": {
                    "kind": "contract-item",
                    "contractId": "surfaces",
                    "itemKind": "surface",
                    "itemId": "main",
                },
                "implementationBoundary": {
                    "status": "verified",
                    "description": "The product surface is implemented.",
                    "locator": "app/main.py",
                },
                "positiveEvidence": [
                    {
                        "id": "surface-positive",
                        "status": "verified",
                        "kind": proof_kind,
                        "description": "Execute the supported path.",
                        "locator": "tests/proof.py",
                        "commandId": "product-proof",
                        "expectedResult": "The supported path succeeds.",
                    }
                ],
                "negativeEvidence": [
                    {
                        "id": "surface-negative",
                        "status": "verified",
                        "kind": proof_kind,
                        "description": "Execute the rejected path.",
                        "locator": "tests/proof.py",
                        "commandId": "product-proof",
                        "expectedResult": "The rejected path fails closed.",
                    }
                ],
                "releaseGateIds": ["product-release"],
            }
        ],
    }


class ExecutableProofSemanticsTests(unittest.TestCase):
    def write_consumer(self, root: Path, evidence: dict) -> None:
        (root / "contracts").mkdir(parents=True, exist_ok=True)
        (root / "tests").mkdir(parents=True, exist_ok=True)
        (root / "app").mkdir(parents=True, exist_ok=True)
        (root / "tests" / "proof.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
        (root / "app" / "main.py").write_text("# product boundary\n", encoding="utf-8")
        (root / "contracts" / "manifest.json").write_text(
            json.dumps(
                {
                    "contracts": [
                        {"id": "surfaces", "versionHistory": [{"version": 1}]}
                    ]
                }
            ),
            encoding="utf-8",
        )
        (root / "contracts" / "implementation-evidence.json").write_text(
            json.dumps(evidence), encoding="utf-8"
        )

    def test_v6_schema_accepts_execution_profile(self) -> None:
        schema = json.loads(IMPLEMENTATION_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(product_evidence())

    def test_end_to_end_label_cannot_upgrade_integration_command(self) -> None:
        evidence = product_evidence(capabilities=["integration"])
        errors = implementation.proof_execution_errors(evidence)
        self.assertTrue(
            any("requires command capability 'end-to-end'" in error for error in errors),
            errors,
        )
        readiness = implementation.release_readiness_errors(evidence)
        self.assertTrue(
            any("requires command capability 'end-to-end'" in error for error in readiness),
            readiness,
        )

    def test_static_inspection_command_cannot_masquerade_as_end_to_end(self) -> None:
        evidence = product_evidence(capabilities=["inspection"])
        errors = implementation.proof_execution_errors(evidence)
        self.assertTrue(any("end-to-end" in error for error in errors), errors)

    def test_unrelated_launcher_cannot_claim_declared_harness(self) -> None:
        evidence = product_evidence()
        evidence["commands"][0]["command"] = "echo tests/proof.py"
        errors = implementation.proof_execution_errors(evidence)
        readiness = implementation.release_readiness_errors(evidence)
        self.assertTrue(
            any("command must exactly invoke declared harness" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("command must exactly invoke declared harness" in error for error in readiness),
            readiness,
        )

    def test_negative_proof_requires_negative_path_capability(self) -> None:
        evidence = product_evidence(supports_negative=False)
        errors = implementation.proof_execution_errors(evidence)
        self.assertTrue(
            any("supportsNegativePath=true" in error for error in errors), errors
        )

    def test_consumer_validation_requires_repository_harness_file(self) -> None:
        evidence = product_evidence()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_consumer(root, evidence)
            self.assertEqual(implementation.validate(root), [])
            (root / "tests" / "proof.py").unlink()
            errors = implementation.validate(root)
        self.assertTrue(any("execution harness does not exist" in error for error in errors), errors)

    def test_release_readiness_with_root_requires_repository_harness_file(self) -> None:
        evidence = product_evidence()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_consumer(root, evidence)
            self.assertEqual(implementation.release_readiness_errors(evidence, root), [])
            (root / "tests" / "proof.py").unlink()
            errors = implementation.release_readiness_errors(evidence, root)
        self.assertTrue(
            any("execution harness does not exist" in error for error in errors),
            errors,
        )

    def test_direct_semantic_paths_reject_unsafe_harness_locators(self) -> None:
        unsafe_locators = (
            "../outside.py",
            "tests/../proof.py",
            "/tmp/proof.py",
            "C:/proof.py",
            ".git/hooks/proof.py",
            "tests\\proof.py",
        )
        for locator in unsafe_locators:
            with self.subTest(locator=locator):
                evidence = product_evidence()
                evidence["commands"][0]["execution"]["harness"]["locator"] = locator
                semantic = implementation.proof_execution_errors(evidence)
                readiness = implementation.release_readiness_errors(evidence)
                self.assertTrue(
                    any("safe repository-relative file path" in error for error in semantic),
                    semantic,
                )
                self.assertTrue(
                    any("safe repository-relative file path" in error for error in readiness),
                    readiness,
                )

    def test_symlink_harness_is_rejected_by_validation_and_release_readiness(self) -> None:
        evidence = product_evidence()
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            root = workspace / "consumer"
            self.write_consumer(root, evidence)
            outside = workspace / "outside.py"
            outside.write_text("raise SystemExit(0)\n", encoding="utf-8")
            harness = root / "tests" / "proof.py"
            harness.unlink()
            try:
                harness.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            structural = implementation.validate(root)
            readiness = implementation.release_readiness_errors(evidence, root)
        self.assertTrue(
            any("regular non-symlink file" in error for error in structural),
            structural,
        )
        self.assertTrue(
            any("regular non-symlink file" in error for error in readiness),
            readiness,
        )

    def test_browser_sensitive_target_requires_browser_command_capability(self) -> None:
        evidence = product_evidence(capabilities=["end-to-end"])
        errors = webapp.browser_level_proof_errors(evidence)
        self.assertTrue(
            any("browser execution capability" in error for error in errors), errors
        )
        evidence["commands"][0]["execution"]["capabilities"].append("browser")
        self.assertEqual(webapp.browser_level_proof_errors(evidence), [])

    def test_accessibility_proof_requires_accessibility_and_browser_capabilities(self) -> None:
        evidence = product_evidence(
            proof_kind="accessibility-test",
            capabilities=["browser"],
        )
        generic = implementation.proof_execution_errors(evidence)
        self.assertTrue(
            any("requires command capability 'accessibility'" in error for error in generic),
            generic,
        )
        evidence["commands"][0]["execution"]["capabilities"].append("accessibility")
        self.assertEqual(implementation.proof_execution_errors(evidence), [])
        self.assertEqual(webapp.browser_level_proof_errors(evidence), [])

    def test_release_execution_harness_must_match_implementation_authority(self) -> None:
        evidence = product_evidence(capabilities=["end-to-end", "browser"])
        execution = {
            "$schema": "../schemas/release-execution.schema.json",
            "schemaVersion": 2,
            "mode": "product",
            "commands": [
                {
                    "commandId": "product-proof",
                    "argv": ["python", "tests/proof.py"],
                    "workingDirectory": ".",
                    "harnessLocator": "tests/proof.py",
                    "harnessArgumentIndex": 1,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "contracts").mkdir(parents=True)
            (root / "contracts" / "implementation-evidence.json").write_text(
                json.dumps(evidence), encoding="utf-8"
            )
            (root / "contracts" / "release-execution.json").write_text(
                json.dumps(execution), encoding="utf-8"
            )
            self.assertEqual(release_execution.validate(root), [])
            execution["commands"][0]["harnessLocator"] = "tests/other.py"
            (root / "contracts" / "release-execution.json").write_text(
                json.dumps(execution), encoding="utf-8"
            )
            errors = release_execution.validate(root)
        self.assertTrue(any("must exactly match" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
