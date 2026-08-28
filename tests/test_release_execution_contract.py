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
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._temp_dir = tempfile.TemporaryDirectory()
        root = Path(cls._temp_dir.name)
        cls.target = root / "consumer"
        config = root / "composition.json"
        config.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "recipe": "webapp",
                    "components": {
                        "include": ["lifecycle.release-bundle"],
                        "exclude": [],
                    },
                    "parameters": {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                str(COMPOSER),
                "apply",
                "--config",
                str(config),
                "--target",
                str(cls.target),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            cls._temp_dir.cleanup()
            raise AssertionError(result.stdout + result.stderr)
        cls._template_implementation = json.loads(
            (cls.target / "contracts/implementation-evidence.json").read_text(
                encoding="utf-8"
            )
        )
        cls._template_execution = json.loads(
            (cls.target / "contracts/release-execution.json").read_text(
                encoding="utf-8"
            )
        )

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._temp_dir.cleanup()
        finally:
            super().tearDownClass()

    def setUp(self) -> None:
        self.write_json(
            self.target / "contracts/implementation-evidence.json",
            self._template_implementation,
        )
        self.write_json(
            self.target / "contracts/release-execution.json",
            self._template_execution,
        )

    def write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def run_validator(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(
                    self.target
                    / ".template-composition/validators/validate_release_execution.py"
                ),
                ".",
            ],
            cwd=self.target,
            text=True,
            capture_output=True,
            check=False,
        )

    def product_implementation(self) -> dict:
        return {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 6,
            "mode": "product",
            "commands": [
                {
                    "id": "product-proof",
                    "command": "python product/prove.py",
                    "purpose": "Run the product proof.",
                    "execution": {
                        "capabilities": ["integration"],
                        "harness": {
                            "kind": "repository-file",
                            "locator": "product/prove.py",
                        },
                        "supportsNegativePath": False,
                    },
                }
            ],
            "releaseGates": [
                {
                    "id": "product-release",
                    "purpose": "Block release unless the proof passes.",
                    "commandIds": ["product-proof"],
                }
            ],
            "requirements": [],
            "records": [],
        }

    def product_execution(self) -> dict:
        return {
            "$schema": "../schemas/release-execution.schema.json",
            "schemaVersion": 2,
            "mode": "product",
            "commands": [
                {
                    "commandId": "product-proof",
                    "argv": ["python", "product/prove.py"],
                    "workingDirectory": ".",
                    "harnessLocator": "product/prove.py",
                    "harnessArgumentIndex": 1,
                }
            ],
        }

    def test_composer_materializes_template_execution_contract_and_validator(self) -> None:
        execution = json.loads(
            (self.target / "contracts/release-execution.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(execution["schemaVersion"], 2)
        self.assertEqual(execution["mode"], "template")
        self.assertEqual(execution["commands"], [])
        self.assertTrue(
            (
                self.target
                / ".template-composition/validators/validate_release_execution.py"
            ).is_file()
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Release execution validation: OK", result.stdout)

    def test_product_execution_exactly_covers_authoritative_commands(self) -> None:
        self.write_json(
            self.target / "contracts/implementation-evidence.json",
            self.product_implementation(),
        )
        self.write_json(
            self.target / "contracts/release-execution.json",
            self.product_execution(),
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        missing = self.product_execution()
        missing["commands"] = []
        self.write_json(self.target / "contracts/release-execution.json", missing)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must exactly cover authoritative commands", result.stderr)

        extra = self.product_execution()
        extra["commands"].append(
            {
                "commandId": "extra-proof",
                "argv": ["python", "product/extra.py"],
                "workingDirectory": ".",
                "harnessLocator": "product/extra.py",
                "harnessArgumentIndex": 1,
            }
        )
        self.write_json(self.target / "contracts/release-execution.json", extra)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must exactly cover authoritative commands", result.stderr)

    def test_harness_locator_must_match_implementation_command(self) -> None:
        self.write_json(
            self.target / "contracts/implementation-evidence.json",
            self.product_implementation(),
        )
        execution = self.product_execution()
        execution["commands"][0]["harnessLocator"] = "product/other.py"
        self.write_json(self.target / "contracts/release-execution.json", execution)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("harnessLocator must exactly match", result.stderr)

    def test_argv_must_exactly_execute_declared_harness(self) -> None:
        self.write_json(
            self.target / "contracts/implementation-evidence.json",
            self.product_implementation(),
        )
        for argv in (
            ["python", "product/other.py"],
            ["echo", "product/prove.py"],
            ["python", "-c", "print('ok')", "product/prove.py"],
        ):
            with self.subTest(argv=argv):
                execution = self.product_execution()
                execution["commands"][0]["argv"] = argv
                self.write_json(
                    self.target / "contracts/release-execution.json", execution
                )
                result = self.run_validator()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "argv must exactly execute declared harness", result.stderr
                )

    def test_harness_argument_is_resolved_from_working_directory(self) -> None:
        self.write_json(
            self.target / "contracts/implementation-evidence.json",
            self.product_implementation(),
        )
        execution = self.product_execution()
        execution["commands"][0].update(
            {
                "argv": ["python", "prove.py"],
                "workingDirectory": "product",
                "harnessArgumentIndex": 1,
            }
        )
        self.write_json(self.target / "contracts/release-execution.json", execution)
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        execution["commands"][0]["workingDirectory"] = "tests"
        self.write_json(self.target / "contracts/release-execution.json", execution)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot be invoked", result.stderr)

    def test_harness_argument_index_is_fixed_by_invocation(self) -> None:
        self.write_json(
            self.target / "contracts/implementation-evidence.json",
            self.product_implementation(),
        )
        execution = self.product_execution()
        execution["commands"][0]["harnessArgumentIndex"] = 2
        self.write_json(self.target / "contracts/release-execution.json", execution)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("harnessArgumentIndex must be 1", result.stderr)

    def test_python_unittest_invocation_has_exact_module_argv(self) -> None:
        implementation = self.product_implementation()
        implementation["commands"][0]["command"] = (
            "python -m unittest tests.test_prove"
        )
        implementation["commands"][0]["execution"]["harness"] = {
            "kind": "repository-file",
            "locator": "tests/test_prove.py",
        }
        execution = self.product_execution()
        execution["commands"][0].update(
            {
                "argv": ["python", "-m", "unittest", "tests.test_prove"],
                "harnessLocator": "tests/test_prove.py",
                "harnessArgumentIndex": 3,
            }
        )
        self.write_json(
            self.target / "contracts/implementation-evidence.json", implementation
        )
        self.write_json(self.target / "contracts/release-execution.json", execution)
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_direct_invocation_has_exact_executable_argv(self) -> None:
        implementation = self.product_implementation()
        implementation["commands"][0]["command"] = "./scripts/verify.sh"
        implementation["commands"][0]["execution"]["harness"] = {
            "kind": "repository-file",
            "locator": "scripts/verify.sh",
        }
        execution = self.product_execution()
        execution["commands"][0].update(
            {
                "argv": ["./scripts/verify.sh"],
                "harnessLocator": "scripts/verify.sh",
                "harnessArgumentIndex": 0,
            }
        )
        self.write_json(
            self.target / "contracts/implementation-evidence.json", implementation
        )
        self.write_json(self.target / "contracts/release-execution.json", execution)
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_execution_mode_must_match_implementation_mode(self) -> None:
        self.write_json(
            self.target / "contracts/implementation-evidence.json",
            self.product_implementation(),
        )
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "product implementation evidence requires product release execution",
            result.stderr,
        )

        self.write_json(
            self.target / "contracts/implementation-evidence.json",
            self._template_implementation,
        )
        self.write_json(
            self.target / "contracts/release-execution.json",
            self.product_execution(),
        )
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "product release execution requires product implementation evidence",
            result.stderr,
        )

    def test_validator_rejects_invalid_argv_elements(self) -> None:
        self.write_json(
            self.target / "contracts/implementation-evidence.json",
            self.product_implementation(),
        )

        for invalid_argument in ("", "proof\x00.py"):
            with self.subTest(invalid_argument=invalid_argument):
                execution = self.product_execution()
                execution["commands"][0]["argv"] = ["python", invalid_argument]
                self.write_json(
                    self.target / "contracts/release-execution.json", execution
                )
                result = self.run_validator()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "argv must be a non-empty array of non-empty NUL-free strings",
                    result.stderr,
                )

    def test_validator_rejects_duplicate_command_ids(self) -> None:
        self.write_json(
            self.target / "contracts/implementation-evidence.json",
            self.product_implementation(),
        )
        execution = self.product_execution()
        execution["commands"].append(
            {
                "commandId": "product-proof",
                "argv": ["python", "product/prove.py"],
                "workingDirectory": ".",
                "harnessLocator": "product/prove.py",
                "harnessArgumentIndex": 1,
            }
        )
        self.write_json(self.target / "contracts/release-execution.json", execution)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "duplicate release execution command commandId: product-proof",
            result.stderr,
        )

    def test_semantic_validator_rejects_unsafe_paths_without_schema_dispatch(self) -> None:
        implementation = self.product_implementation()
        self.write_json(
            self.target / "contracts/implementation-evidence.json", implementation
        )

        unsafe_harness = self.product_execution()
        implementation["commands"][0]["execution"]["harness"]["locator"] = (
            "../outside.py"
        )
        unsafe_harness["commands"][0].update(
            {
                "argv": ["python", "../outside.py"],
                "harnessLocator": "../outside.py",
            }
        )
        self.write_json(
            self.target / "contracts/implementation-evidence.json", implementation
        )
        self.write_json(
            self.target / "contracts/release-execution.json", unsafe_harness
        )
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "harnessLocator must be a safe repository-relative file path",
            result.stderr,
        )

        implementation = self.product_implementation()
        self.write_json(
            self.target / "contracts/implementation-evidence.json", implementation
        )
        unsafe_cwd = self.product_execution()
        unsafe_cwd["commands"][0]["workingDirectory"] = "../outside"
        self.write_json(
            self.target / "contracts/release-execution.json", unsafe_cwd
        )
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "workingDirectory must be a safe repository-relative directory",
            result.stderr,
        )

    def test_schema_rejects_unsafe_paths_and_empty_argv(self) -> None:
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

        for unsafe in (
            "..",
            "../product",
            "/tmp",
            "C:/tmp",
            ".git",
            "product/../tmp",
        ):
            with self.subTest(workingDirectory=unsafe):
                document = self.product_execution()
                document["commands"][0]["workingDirectory"] = unsafe
                self.assertTrue(list(validator.iter_errors(document)))
            with self.subTest(harnessLocator=unsafe):
                document = self.product_execution()
                document["commands"][0]["harnessLocator"] = unsafe
                self.assertTrue(list(validator.iter_errors(document)))

        empty_argv = self.product_execution()
        empty_argv["commands"][0]["argv"] = []
        self.assertTrue(list(validator.iter_errors(empty_argv)))

        missing_index = self.product_execution()
        del missing_index["commands"][0]["harnessArgumentIndex"]
        self.assertTrue(list(validator.iter_errors(missing_index)))


if __name__ == "__main__":
    unittest.main()
