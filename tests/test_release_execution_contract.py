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


class ReleaseExecutionContractTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def materialize_webapp(self, root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        target = root / "consumer"
        config = root / "composition.json"
        self.write_json(
            config,
            {
                "schema_version": 1,
                "recipe": "webapp",
                "components": {"include": [], "exclude": []},
                "parameters": {},
            },
        )
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

    def run_validator(self, target: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(
                    target
                    / ".template-composition/validators/validate_release_execution.py"
                ),
                ".",
            ],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )

    def product_implementation(self) -> dict:
        return {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "commands": [
                {
                    "id": "product-proof",
                    "command": "python product/prove.py",
                    "purpose": "Run the product proof.",
                }
            ],
            "releaseGates": [
                {
                    "id": "product-release",
                    "purpose": "Block release unless the proof passes.",
                    "commandIds": ["product-proof"],
                }
            ],
            "records": [],
        }

    def product_execution(self) -> dict:
        return {
            "$schema": "../schemas/release-execution.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "commands": [
                {
                    "commandId": "product-proof",
                    "argv": ["python", "product/prove.py"],
                    "workingDirectory": ".",
                }
            ],
        }

    def test_composer_materializes_template_execution_contract_and_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            execution = json.loads(
                (target / "contracts/release-execution.json").read_text(encoding="utf-8")
            )
            self.assertEqual(execution["mode"], "template")
            self.assertEqual(execution["commands"], [])
            result = self.run_validator(target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Release execution validation: OK", result.stdout)

    def test_product_execution_exactly_covers_authoritative_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            self.write_json(
                target / "contracts/implementation-evidence.json",
                self.product_implementation(),
            )
            self.write_json(
                target / "contracts/release-execution.json",
                self.product_execution(),
            )
            result = self.run_validator(target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            missing = self.product_execution()
            missing["commands"] = []
            self.write_json(target / "contracts/release-execution.json", missing)
            result = self.run_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must exactly cover authoritative commands", result.stderr)

            extra = self.product_execution()
            extra["commands"].append(
                {
                    "commandId": "extra-proof",
                    "argv": ["python", "product/extra.py"],
                    "workingDirectory": ".",
                }
            )
            self.write_json(target / "contracts/release-execution.json", extra)
            result = self.run_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must exactly cover authoritative commands", result.stderr)

    def test_execution_mode_must_match_implementation_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            self.write_json(
                target / "contracts/implementation-evidence.json",
                self.product_implementation(),
            )
            result = self.run_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "product implementation evidence requires product release execution",
                result.stderr,
            )

            target = self.materialize_webapp(Path(temp_dir) / "inverse")
            self.write_json(
                target / "contracts/release-execution.json",
                self.product_execution(),
            )
            result = self.run_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "product release execution requires product implementation evidence",
                result.stderr,
            )

    def test_validator_rejects_invalid_argv_elements(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            self.write_json(
                target / "contracts/implementation-evidence.json",
                self.product_implementation(),
            )

            for invalid_argument in ("", "proof\x00.py"):
                with self.subTest(invalid_argument=invalid_argument):
                    execution = self.product_execution()
                    execution["commands"][0]["argv"] = ["python", invalid_argument]
                    self.write_json(
                        target / "contracts/release-execution.json", execution
                    )
                    result = self.run_validator(target)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(
                        "argv must be a non-empty array of non-empty NUL-free strings",
                        result.stderr,
                    )

    def test_validator_rejects_duplicate_command_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            self.write_json(
                target / "contracts/implementation-evidence.json",
                self.product_implementation(),
            )
            execution = self.product_execution()
            execution["commands"].append(
                {
                    "commandId": "product-proof",
                    "argv": ["python", "product/alternate.py"],
                    "workingDirectory": ".",
                }
            )
            self.write_json(target / "contracts/release-execution.json", execution)
            result = self.run_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "duplicate release execution command commandId: product-proof",
                result.stderr,
            )

    def test_schema_rejects_unsafe_working_directories_and_empty_argv(self) -> None:
        schema = json.loads(
            (
                ROOT
                / "components/lifecycle.release-execution/files/schemas/release-execution.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)

        valid = self.product_execution()
        self.assertEqual(list(validator.iter_errors(valid)), [])

        for unsafe in ("..", "../product", "/tmp", "C:/tmp", ".git", "product/../tmp"):
            with self.subTest(workingDirectory=unsafe):
                document = self.product_execution()
                document["commands"][0]["workingDirectory"] = unsafe
                self.assertTrue(list(validator.iter_errors(document)))

        empty_argv = self.product_execution()
        empty_argv["commands"][0]["argv"] = []
        self.assertTrue(list(validator.iter_errors(empty_argv)))


if __name__ == "__main__":
    unittest.main()
