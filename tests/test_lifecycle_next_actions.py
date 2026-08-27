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

    def project(self, mode: str, status: str = "valid", checks: list[dict] | None = None) -> dict:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence = root / "contracts" / "implementation-evidence.json"
            evidence.parent.mkdir()
            evidence.write_text(json.dumps({"mode": mode}), encoding="utf-8")
            value = runner._lifecycle_projection(root, status, checks or [])
            self.schema_validator.validate(value)
            return value

    def test_planning_is_scaffold_only_and_has_product_next_actions(self) -> None:
        value = self.project("planning")
        self.assertEqual(value["lifecycle_stage"], "scaffold-valid")
        self.assertEqual(value["implementation_evidence_mode"], "planning")
        self.assertEqual(value["release_readiness"], "not-evaluated")
        self.assertIn("implement-product", value["next_actions"])
        self.assertIn("populate-product-evidence", value["next_actions"])
        self.assertIn("check-release-readiness", value["next_actions"])

    def test_template_is_not_an_implemented_product(self) -> None:
        value = self.project("template")
        self.assertEqual(value["lifecycle_stage"], "scaffold-valid")
        self.assertIn("define-product-requirements", value["next_actions"])
        self.assertNotEqual(value["lifecycle_stage"], "implemented-product")

    def test_deferred_proof_never_projects_release_ready(self) -> None:
        value = self.project("product", checks=[{"id": "browser-proof", "status": "deferred"}])
        self.assertEqual(value["lifecycle_stage"], "implemented-product")
        self.assertEqual(value["release_readiness"], "not-ready")
        self.assertEqual(value["deferred_checks"], ["browser-proof"])
        self.assertNotIn("release-ready", value["next_actions"])

    def test_product_validation_separates_release_readiness(self) -> None:
        value = self.project("product")
        self.assertEqual(value["lifecycle_stage"], "implemented-product")
        self.assertEqual(value["release_readiness"], "not-evaluated")
        self.assertEqual(value["next_actions"], ["check-release-readiness"])

        ready = self.project("product", checks=[{"id": "release-readiness", "status": "passed"}])
        self.assertEqual(ready["lifecycle_stage"], "release-ready")
        self.assertEqual(ready["release_readiness"], "ready")
        self.assertEqual(ready["next_actions"], [])


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
