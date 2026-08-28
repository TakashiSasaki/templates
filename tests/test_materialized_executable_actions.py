from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


class MaterializedExecutableActionTests(unittest.TestCase):
    def materialize_webapp(self, work: Path) -> Path:
        config = work / "composition.json"
        config.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "recipe": "webapp",
                    "components": {"include": [], "exclude": []},
                    "parameters": {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        target = work / "consumer"
        result = subprocess.run(
            [
                sys.executable,
                str(COMPOSER),
                "apply",
                "--config",
                str(config),
                "--target",
                str(target),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return target

    def resolve_caller_inputs(
        self,
        argv: list[str],
        values: dict[str, str],
    ) -> list[str]:
        resolved: list[str] = []
        for token in argv:
            resolved.append(values.get(token, token))
        return resolved

    def validate_output(self, target: Path, schema_path: str, output: object) -> None:
        schema = json.loads((target / schema_path).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(output)

    def test_materialized_release_readiness_executes_registry_argv_without_reconstruction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            registry = json.loads(
                (target / ".template-composition/implementation-evidence-actions.json").read_text(
                    encoding="utf-8"
                )
            )
            action = registry["actions"]["check-release-readiness"]
            argv = self.resolve_caller_inputs(
                action["argv"],
                {"{python}": sys.executable},
            )
            self.assertEqual(
                argv[1:],
                [
                    ".template-composition/run_action.py",
                    "check-release-readiness",
                ],
            )
            result = subprocess.run(
                argv,
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            output = json.loads(result.stdout)
            self.validate_output(target, action["output_schema"], output)
            self.assertEqual(output["release_readiness"], "not-ready")
            self.assertEqual(output["$schema"], action["output_schema"])
            self.assertNotIn("contract_common", result.stderr)

    def test_materialized_checkpoint_failure_is_structured_and_self_describing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            registry = json.loads(
                (target / ".template-composition/lifecycle-checkpoint-actions.json").read_text(
                    encoding="utf-8"
                )
            )
            action = registry["actions"]["create-planning-checkpoint"]
            argv = self.resolve_caller_inputs(
                action["argv"],
                {
                    "{python}": sys.executable,
                    "{checkpoint_id}": "e2e-planning",
                },
            )
            result = subprocess.run(
                argv,
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            output = json.loads(result.stdout)
            schema_path = output["$schema"]
            self.validate_output(target, schema_path, output)
            self.assertEqual(output["action"], "create-planning-checkpoint")
            self.assertEqual(output["status"], "failed")
            self.assertIn("planning", output["error"])


if __name__ == "__main__":
    unittest.main()
