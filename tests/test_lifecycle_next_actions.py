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

SPEC = importlib.util.spec_from_file_location("composition_validation_runner", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Composition validation runner")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class LifecycleNextActionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        cls.schema_validator = Draft202012Validator(schema)

    def project(
        self,
        mode: str,
        status: str = "valid",
        checks: list[dict] | None = None,
        *,
        checkpoints_selected: bool = False,
        checkpoint_phase: str | None = None,
        malformed_checkpoint_ledger: bool = False,
    ) -> dict:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence = root / "contracts" / "implementation-evidence.json"
            evidence.parent.mkdir()
            evidence.write_text(json.dumps({"mode": mode}), encoding="utf-8")

            active_checks = list(checks or [])
            if checkpoints_selected:
                active_checks.append(
                    {
                        "id": "lifecycle-checkpoints",
                        "component": "lifecycle.lifecycle-checkpoints",
                        "status": "passed",
                    }
                )
                ledger = root / "contracts" / "lifecycle-checkpoints.json"
                if malformed_checkpoint_ledger:
                    ledger.write_text(
                        json.dumps({"checkpoints": "not-an-array"}),
                        encoding="utf-8",
                    )
                else:
                    checkpoints = []
                    if checkpoint_phase is not None:
                        checkpoints.append({"phase": checkpoint_phase})
                    ledger.write_text(
                        json.dumps({"checkpoints": checkpoints}),
                        encoding="utf-8",
                    )

            value = runner._lifecycle_projection(root, status, active_checks)
            self.schema_validator.validate(value)
            return value

    def test_planning_without_checkpoint_component_preserves_product_actions(self) -> None:
        value = self.project("planning")
        self.assertEqual(value["lifecycle_stage"], "scaffold-valid")
        self.assertEqual(value["implementation_evidence_mode"], "planning")
        self.assertIn("implement-product", value["next_actions"])
        self.assertIn("check-release-readiness", value["next_actions"])

    def test_selected_checkpoints_require_planning_checkpoint_before_coding(self) -> None:
        value = self.project("planning", checkpoints_selected=True)
        self.assertEqual(value["lifecycle_stage"], "scaffold-valid")
        self.assertEqual(
            value["blocking_conditions"],
            ["implementation-evidence-planning", "planning-checkpoint-required"],
        )
        self.assertEqual(value["next_actions"], ["create-planning-checkpoint"])
        self.assertNotIn("implement-product", value["next_actions"])

    def test_planning_checkpoint_unlocks_product_implementation(self) -> None:
        value = self.project(
            "planning",
            checkpoints_selected=True,
            checkpoint_phase="planning",
        )
        self.assertIn("implement-product", value["next_actions"])
        self.assertIn("validate-product-state", value["next_actions"])
        self.assertNotIn("check-release-readiness", value["next_actions"])

    def test_previous_product_checkpoint_requires_new_planning_checkpoint(self) -> None:
        value = self.project(
            "planning",
            checkpoints_selected=True,
            checkpoint_phase="product",
        )
        self.assertEqual(value["next_actions"], ["create-planning-checkpoint"])
        self.assertNotIn("implement-product", value["next_actions"])

    def test_product_requires_product_checkpoint_before_release_readiness(self) -> None:
        value = self.project(
            "product",
            checkpoints_selected=True,
            checkpoint_phase="planning",
        )
        self.assertEqual(value["lifecycle_stage"], "implemented-product")
        self.assertEqual(value["release_readiness"], "not-evaluated")
        self.assertEqual(value["blocking_conditions"], ["product-checkpoint-required"])
        self.assertEqual(value["next_actions"], ["create-product-checkpoint"])
        self.assertNotIn("check-release-readiness", value["next_actions"])

    def test_product_checkpoint_unlocks_release_readiness(self) -> None:
        value = self.project(
            "product",
            checkpoints_selected=True,
            checkpoint_phase="product",
        )
        self.assertEqual(value["next_actions"], ["check-release-readiness"])

    def test_release_ready_check_cannot_skip_product_checkpoint(self) -> None:
        value = self.project(
            "product",
            checks=[{"id": "release-readiness", "status": "passed"}],
            checkpoints_selected=True,
            checkpoint_phase="planning",
        )
        self.assertEqual(value["lifecycle_stage"], "implemented-product")
        self.assertEqual(value["release_readiness"], "not-evaluated")
        self.assertEqual(value["next_actions"], ["create-product-checkpoint"])

    def test_deferred_proof_waits_behind_missing_product_checkpoint(self) -> None:
        value = self.project(
            "product",
            checks=[{"id": "browser-proof", "status": "deferred"}],
            checkpoints_selected=True,
            checkpoint_phase="planning",
        )
        self.assertEqual(value["release_readiness"], "not-ready")
        self.assertEqual(
            value["blocking_conditions"],
            ["product-checkpoint-required", "deferred-proof"],
        )
        self.assertEqual(value["deferred_checks"], ["browser-proof"])
        self.assertEqual(value["next_actions"], ["create-product-checkpoint"])

    def test_deferred_proof_never_projects_release_ready(self) -> None:
        value = self.project(
            "product", checks=[{"id": "browser-proof", "status": "deferred"}]
        )
        self.assertEqual(value["lifecycle_stage"], "implemented-product")
        self.assertEqual(value["release_readiness"], "not-ready")
        self.assertEqual(value["deferred_checks"], ["browser-proof"])
        self.assertNotIn("release-ready", value["next_actions"])

    def test_product_validation_separates_release_readiness(self) -> None:
        value = self.project("product")
        self.assertEqual(value["lifecycle_stage"], "implemented-product")
        self.assertEqual(value["release_readiness"], "not-evaluated")
        self.assertEqual(value["next_actions"], ["check-release-readiness"])

        ready = self.project(
            "product", checks=[{"id": "release-readiness", "status": "passed"}]
        )
        self.assertEqual(ready["lifecycle_stage"], "release-ready")
        self.assertEqual(ready["release_readiness"], "ready")
        self.assertEqual(ready["next_actions"], [])

    def test_selected_template_does_not_expose_product_coding(self) -> None:
        value = self.project("template", checkpoints_selected=True)
        self.assertEqual(value["next_actions"], ["define-product-requirements"])
        self.assertNotIn("implement-product", value["next_actions"])

    def test_malformed_selected_checkpoint_ledger_fails_closed(self) -> None:
        value = self.project(
            "planning",
            checkpoints_selected=True,
            malformed_checkpoint_ledger=True,
        )
        self.assertEqual(value["lifecycle_stage"], "composition-invalid")
        self.assertEqual(value["blocking_conditions"], ["checkpoint-state-invalid"])
        self.assertEqual(value["next_actions"], ["inspect", "plan", "apply", "validate"])

    def test_missing_evidence_is_explicitly_scaffold_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            value = runner._lifecycle_projection(Path(temp_dir), "valid", [])
        self.schema_validator.validate(value)
        self.assertEqual(value["implementation_evidence_mode"], "missing")
        self.assertEqual(value["blocking_conditions"], ["implementation-evidence-missing"])
        self.assertEqual(value["lifecycle_stage"], "scaffold-valid")

    def test_malformed_evidence_is_invalid_not_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence = root / "contracts" / "implementation-evidence.json"
            evidence.parent.mkdir()
            evidence.write_text("{", encoding="utf-8")
            self.assertEqual(runner._evidence_mode(root), "invalid")

    def test_check_failure_is_invalid_even_with_valid_status(self) -> None:
        value = self.project(
            "product", checks=[{"id": "webapp-contracts", "status": "failed"}]
        )
        self.assertEqual(value["lifecycle_stage"], "composition-invalid")
        self.assertEqual(
            value["blocking_conditions"], ["composition-validation-failed"]
        )

    def test_deferred_check_ids_are_sorted(self) -> None:
        value = self.project(
            "product",
            checks=[
                {"id": "release-evidence-template", "status": "deferred"},
                {"id": "browser-proof", "status": "deferred"},
            ],
        )
        self.assertEqual(
            value["deferred_checks"],
            ["browser-proof", "release-evidence-template"],
        )

    def test_invalid_evidence_fails_closed_to_repair_actions(self) -> None:
        value = self.project("unexpected-mode")
        self.assertEqual(value["lifecycle_stage"], "composition-invalid")
        self.assertEqual(
            value["blocking_conditions"], ["implementation-evidence-invalid"]
        )
        self.assertEqual(value["next_actions"], ["inspect", "plan", "apply", "validate"])

    def test_invalid_composition_fails_closed_to_repair_actions(self) -> None:
        value = self.project("product", status="invalid")
        self.assertEqual(value["lifecycle_stage"], "composition-invalid")
        self.assertEqual(value["release_readiness"], "not-evaluated")
        self.assertEqual(value["next_actions"], ["inspect", "plan", "apply", "validate"])


if __name__ == "__main__":
    unittest.main()
