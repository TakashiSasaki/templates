from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_webapp_productization_acceptance as product_helpers

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
REGISTRY = (
    ROOT
    / "components"
    / "lifecycle.composition-state"
    / "files"
    / ".template-composition"
    / "validation-registry.json"
)


class SelectedComponentValidationTests(unittest.TestCase):
    def write_config(self, root: Path, recipe: str) -> Path:
        path = root / "composition.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "recipe": recipe,
                    "components": {"include": [], "exclude": []},
                    "parameters": {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def apply(self, target: Path, config_path: Path) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(COMPOSER),
                "apply",
                "--config",
                str(config_path),
                "--target",
                str(target),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def run_consumer_validation(self, target: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
        runner = target / ".template-composition" / "validate.py"
        result = subprocess.run(
            [sys.executable, str(runner), str(target), "--format", "json"],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"consumer validator did not emit JSON: {exc}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        return result, payload

    def run_public_validation(self, target: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [sys.executable, str(COMPOSER), "validate", "--target", str(target)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"public validation did not emit JSON: {exc}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        return result, payload

    def test_registry_entrypoints_are_managed_by_the_declared_components(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(registry["schema_version"], 1)
        ids: list[str] = []
        for validator in registry["validators"]:
            ids.append(validator["id"])
            descriptor = json.loads(
                (ROOT / "components" / validator["component"] / "component.json").read_text(
                    encoding="utf-8"
                )
            )
            materials = {
                material["destination"]: material for material in descriptor["materials"]
            }
            self.assertIn(validator["entrypoint"], materials, validator["id"])
            self.assertEqual(
                materials[validator["entrypoint"]]["ownership"],
                "managed",
                validator["id"],
            )
            condition = validator.get("when")
            if condition is not None:
                self.assertIn(condition["document"], materials, validator["id"])
        self.assertEqual(len(ids), len(set(ids)))

    def test_minimal_skill_runs_only_selected_component_validators(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            self.apply(target, self.write_config(root, "skill"))

            result, payload = self.run_consumer_validation(target)
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(payload["status"], "valid")
            self.assertEqual(
                payload["resolved_components"],
                ["artifact.skill-core", "lifecycle.composition-state"],
            )
            self.assertEqual(
                [(check["id"], check["status"]) for check in payload["checks"]],
                [
                    ("composition-state", "passed"),
                    ("skill-scaffold", "passed"),
                ],
            )
            self.assertFalse(
                any(check["id"].startswith("release-") for check in payload["checks"])
            )

            public_result, public_payload = self.run_public_validation(target)
            self.assertEqual(public_result.returncode, 0, public_payload)
            self.assertEqual(public_payload["status"], "valid")
            self.assertEqual(
                [check["id"] for check in public_payload["checks"]],
                ["composition-state", "skill-scaffold"],
            )

            runner = target / ".template-composition" / "validate.py"
            human = subprocess.run(
                [sys.executable, str(runner), str(target)],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(human.returncode, 0, human.stdout + human.stderr)
            self.assertIn("PASSED: composition-state", human.stdout)
            self.assertIn("PASSED: skill-scaffold", human.stdout)
            self.assertIn("Composition validation: VALID", human.stdout)

    def test_webapp_runs_full_current_selected_validation_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            self.apply(target, self.write_config(root, "webapp"))

            result, payload = self.run_consumer_validation(target)
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(payload["status"], "valid")
            component_ids = set(payload["resolved_components"])
            self.assertIn("lifecycle.release-bundle", component_ids)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(
                set(checks),
                {
                    "composition-state",
                    "webapp-contracts",
                    "webapp-implementation-coverage",
                    "contract-evolution",
                    "implementation-evidence",
                    "release-execution",
                    "release-evidence-template",
                    "release-bundle-template",
                },
            )
            self.assertTrue(all(check["status"] == "passed" for check in checks.values()))

    def test_product_release_checks_are_explicitly_deferred(self) -> None:
        helper = product_helpers.WebappProductizationAcceptanceTests(
            methodName="test_composer_generated_webapp_reaches_revision_bound_product_release"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            target, _revision = helper.create_product_candidate(Path(temp_dir))
            result, payload = self.run_consumer_validation(target)
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(payload["status"], "valid")
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["release-evidence-template"]["status"], "deferred")
            self.assertEqual(checks["release-bundle-template"]["status"], "deferred")
            for check_id in ("release-evidence-template", "release-bundle-template"):
                self.assertIn("revision-bound", checks[check_id]["stderr"])
                self.assertIn("exact-candidate", checks[check_id]["stderr"])

    def test_tampered_managed_validator_halts_before_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            self.apply(target, self.write_config(root, "skill"))
            validator = target / ".github" / "scripts" / "validate_skill.py"
            validator.write_text(
                validator.read_text(encoding="utf-8") + "\n# tampered\n",
                encoding="utf-8",
            )

            result, payload = self.run_consumer_validation(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["status"], "invalid")
            self.assertEqual(payload["resolved_components"], [])
            self.assertEqual(payload["checks"][0]["id"], "composition-state")
            self.assertEqual(payload["checks"][0]["status"], "failed")
            self.assertIn("managed material differs", payload["checks"][0]["stderr"])

    def test_registry_cannot_dispatch_entrypoint_owned_by_another_component(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            self.apply(target, self.write_config(root, "skill"))

            registry_path = target / ".template-composition" / "validation-registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            skill_entry = next(
                entry for entry in registry["validators"] if entry["id"] == "skill-scaffold"
            )
            skill_entry["entrypoint"] = ".template-composition/validate_composition.py"
            registry_bytes = (json.dumps(registry, indent=2) + "\n").encode("utf-8")
            registry_path.write_bytes(registry_bytes)

            lock_path = target / ".template-composition" / "lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            registry_lock = next(
                entry
                for entry in lock["files"]
                if entry["destination"] == ".template-composition/validation-registry.json"
            )
            registry_lock["materialized_sha256"] = hashlib.sha256(registry_bytes).hexdigest()
            lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

            result, payload = self.run_consumer_validation(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["status"], "invalid")
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["composition-state"]["status"], "passed")
            self.assertEqual(checks["skill-scaffold"]["status"], "failed")
            self.assertIn("owner mismatch", checks["skill-scaffold"]["stderr"])

    def test_public_validate_rejects_mode_options_in_any_position(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            self.apply(target, self.write_config(root, "skill"))
            for arguments in (
                ["validate", "--mode", "initial", "--target", str(target)],
                ["--mode", "update", "validate", "--target", str(target)],
                ["validate", "--mode=upgrade", "--target", str(target)],
            ):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [sys.executable, str(COMPOSER), *arguments],
                        cwd=ROOT,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("unrecognized arguments", result.stderr)

    def test_webapp_workflow_uses_one_component_aware_entrypoint(self) -> None:
        workflow = (
            ROOT
            / "components"
            / "artifact.webapp-core"
            / "files"
            / ".github"
            / "workflows"
            / "validate-webapp.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("python .template-composition/validate.py .", workflow)
        self.assertNotIn("validate_release_execution.py", workflow)
        self.assertNotIn("release-modes", workflow)
        self.assertNotIn("shell: bash", workflow)


if __name__ == "__main__":
    unittest.main()
