from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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
