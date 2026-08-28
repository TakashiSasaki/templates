from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "components/lifecycle.composition-state/files/.template-composition/validate.py"
SCHEMA_PATH = ROOT / "components/lifecycle.composition-state/files/.template-composition/lifecycle-next-actions.schema.json"
WEBAPP_REGISTRY = ROOT / "components/artifact.webapp-core/files/.template-composition/webapp-actions.json"
READINESS_REGISTRY = ROOT / "components/lifecycle.implementation-evidence/files/.template-composition/implementation-evidence-actions.json"
CHECKPOINT_REGISTRY = ROOT / "components/lifecycle.lifecycle-checkpoints/files/.template-composition/lifecycle-checkpoint-actions.json"
RELEASE_EXECUTION_REGISTRY = ROOT / "components/lifecycle.release-execution/files/.template-composition/release-execution-actions.json"

SPEC = importlib.util.spec_from_file_location("composition_validation_runner_with_prerequisites", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Composition validation runner")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class LifecyclePrerequisiteProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        cls.schema_validator = Draft202012Validator(schema)
        cls.webapp_registry = WEBAPP_REGISTRY.read_text(encoding="utf-8")
        cls.readiness_registry = READINESS_REGISTRY.read_text(encoding="utf-8")
        cls.checkpoint_registry = CHECKPOINT_REGISTRY.read_text(encoding="utf-8")
        cls.release_execution_registry = RELEASE_EXECUTION_REGISTRY.read_text(encoding="utf-8")

    @staticmethod
    def _evidence(*, deferred: bool, browser: bool) -> dict:
        status = "deferred" if deferred else "verified"
        capabilities = ["browser", "end-to-end"] if browser else ["integration"]
        return {
            "mode": "product",
            "commands": [
                {
                    "id": "prove-feature",
                    "execution": {"capabilities": capabilities},
                }
            ],
            "records": [
                {
                    "id": "feature-record",
                    "positiveEvidence": [
                        {
                            "id": "feature-proof",
                            "status": status,
                            "commandId": "prove-feature",
                        }
                    ],
                    "negativeEvidence": [],
                }
            ],
        }

    def _project(
        self,
        evidence: dict,
        *,
        webapp_selected: bool = True,
        malformed_webapp_registry: bool = False,
        checkpoint_phase: str | None = None,
        release_execution_selected: bool = False,
        malformed_release_registry: bool = False,
    ) -> dict:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "contracts").mkdir()
            (root / ".template-composition").mkdir()
            (root / "contracts/implementation-evidence.json").write_text(
                json.dumps(evidence), encoding="utf-8"
            )
            (root / ".template-composition/implementation-evidence-actions.json").write_text(
                self.readiness_registry, encoding="utf-8"
            )
            checks = [
                {
                    "id": "implementation-evidence",
                    "component": "lifecycle.implementation-evidence",
                    "status": "passed",
                }
            ]
            if webapp_selected:
                (root / ".template-composition/webapp-actions.json").write_text(
                    "{}" if malformed_webapp_registry else self.webapp_registry,
                    encoding="utf-8",
                )
                checks.append(
                    {
                        "id": "webapp-implementation-coverage",
                        "component": "artifact.webapp-core",
                        "status": "passed",
                    }
                )
            if checkpoint_phase is not None:
                (root / ".template-composition/lifecycle-checkpoint-actions.json").write_text(
                    self.checkpoint_registry, encoding="utf-8"
                )
                (root / "contracts/lifecycle-checkpoints.json").write_text(
                    json.dumps(
                        {
                            "checkpoints": [
                                {
                                    "phase": checkpoint_phase,
                                    "id": "planning-1" if checkpoint_phase == "planning" else "product-1",
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                checks.append(
                    {
                        "id": "lifecycle-checkpoints",
                        "component": "lifecycle.lifecycle-checkpoints",
                        "status": "passed",
                    }
                )
            if release_execution_selected:
                (root / ".template-composition/release-execution-actions.json").write_text(
                    "{}" if malformed_release_registry else self.release_execution_registry,
                    encoding="utf-8",
                )
                checks.append(
                    {
                        "id": "release-execution",
                        "component": "lifecycle.release-execution",
                        "status": "passed",
                    }
                )
            value = runner._lifecycle_projection(root, "valid", checks)
            self.schema_validator.validate(value)
            return value

    def test_browser_deferred_proof_projects_provider_owned_diagnostic(self) -> None:
        value = self._project(self._evidence(deferred=True, browser=True))
        self.assertEqual(value["schema_version"], 3)
        self.assertEqual(value["lifecycle_stage"], "implemented-product")
        self.assertEqual(value["release_readiness"], "not-ready")
        self.assertEqual(value["deferred_proofs"], ["feature-proof"])
        self.assertEqual(value["next_actions"][0], "resolve-deferred-proof")
        self.assertEqual(
            value["next_action_command"],
            {
                "action": "diagnose-browser-prerequisites",
                "argv": [
                    "{python}",
                    ".template-composition/run_action.py",
                    "diagnose-browser-prerequisites",
                    "--browser-binary",
                    "{browser_binary}",
                    "--webdriver",
                    "{webdriver}",
                    "--compatibility",
                    "{compatibility}",
                    "--localhost",
                    "{localhost}",
                ],
                "caller_inputs": [
                    "{python}",
                    "{browser_binary}",
                    "{webdriver}",
                    "{compatibility}",
                    "{localhost}",
                ],
                "output_schema": ".template-composition/browser-proof-diagnostics.schema.json",
            },
        )
        self.assertEqual(value["conditional_prerequisite_commands"], [])

    def test_generic_deferred_proof_does_not_mislabel_readiness_as_next_command(self) -> None:
        value = self._project(self._evidence(deferred=True, browser=False))
        self.assertEqual(value["release_readiness"], "not-ready")
        self.assertEqual(value["deferred_proofs"], ["feature-proof"])
        self.assertEqual(value["next_actions"][0], "resolve-deferred-proof")
        self.assertNotIn("next_action_command", value)

    def test_product_checkpoint_keeps_precedence_over_browser_diagnostic(self) -> None:
        value = self._project(
            self._evidence(deferred=True, browser=True),
            checkpoint_phase="planning",
        )
        self.assertEqual(value["deferred_proofs"], ["feature-proof"])
        self.assertEqual(value["next_actions"], ["create-product-checkpoint"])
        self.assertEqual(value["next_action_command"]["action"], "create-product-checkpoint")

    def test_malformed_selected_webapp_registry_fails_closed(self) -> None:
        value = self._project(
            self._evidence(deferred=True, browser=True),
            malformed_webapp_registry=True,
        )
        self.assertEqual(value["lifecycle_stage"], "composition-invalid")
        self.assertEqual(
            value["blocking_conditions"],
            ["browser-diagnostic-command-registry-invalid"],
        )
        self.assertEqual(value["deferred_proofs"], ["feature-proof"])
        self.assertNotIn("next_action_command", value)
        self.assertEqual(value["conditional_prerequisite_commands"], [])

    def test_browser_capability_without_webapp_component_remains_generic(self) -> None:
        value = self._project(
            self._evidence(deferred=True, browser=True),
            webapp_selected=False,
        )
        self.assertEqual(value["release_readiness"], "not-ready")
        self.assertEqual(value["deferred_proofs"], ["feature-proof"])
        self.assertNotIn("next_action_command", value)

    def test_verified_browser_proof_preserves_release_readiness_check(self) -> None:
        value = self._project(self._evidence(deferred=False, browser=True))
        self.assertEqual(value["deferred_proofs"], [])
        self.assertEqual(value["release_readiness"], "not-evaluated")
        self.assertEqual(value["next_actions"], ["check-release-readiness"])
        self.assertEqual(value["next_action_command"]["action"], "check-release-readiness")
        self.assertEqual(value["conditional_prerequisite_commands"], [])

    def test_release_execution_projects_conditional_exact_candidate_action(self) -> None:
        value = self._project(
            self._evidence(deferred=False, browser=False),
            release_execution_selected=True,
        )
        self.assertEqual(
            value["conditional_prerequisite_commands"],
            [
                {
                    "condition": "before-release-production",
                    "action": "verify-release-candidate",
                    "argv": [
                        "{python}",
                        ".template-composition/run_action.py",
                        "verify-release-candidate",
                        "{revision}",
                    ],
                    "caller_inputs": ["{python}", "{revision}"],
                    "output_schema": ".template-composition/release-candidate-verification.schema.json",
                }
            ],
        )

    def test_git_candidate_prerequisite_is_not_global(self) -> None:
        value = self._project(self._evidence(deferred=False, browser=False))
        self.assertEqual(value["conditional_prerequisite_commands"], [])
        self.assertNotIn("verify-release-candidate", value["next_actions"])

    def test_malformed_selected_release_registry_fails_closed(self) -> None:
        value = self._project(
            self._evidence(deferred=False, browser=False),
            release_execution_selected=True,
            malformed_release_registry=True,
        )
        self.assertEqual(value["lifecycle_stage"], "composition-invalid")
        self.assertEqual(
            value["blocking_conditions"],
            ["release-candidate-command-registry-invalid"],
        )
        self.assertEqual(value["conditional_prerequisite_commands"], [])
        self.assertNotIn("next_action_command", value)

    def test_browser_resolution_and_release_prerequisite_coexist(self) -> None:
        value = self._project(
            self._evidence(deferred=True, browser=True),
            release_execution_selected=True,
        )
        self.assertEqual(
            value["next_action_command"]["action"],
            "diagnose-browser-prerequisites",
        )
        self.assertEqual(
            value["conditional_prerequisite_commands"][0]["action"],
            "verify-release-candidate",
        )
        self.assertEqual(
            value["conditional_prerequisite_commands"][0]["condition"],
            "before-release-production",
        )


if __name__ == "__main__":
    unittest.main()
