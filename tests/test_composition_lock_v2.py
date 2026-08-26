from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
LOCK_SCHEMA = ROOT / "schemas" / "composition-lock.schema.json"
LOCK_EXAMPLE = ROOT / "examples" / "composition-lock.webapp-mcp.json"


class CompositionLockV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(LOCK_SCHEMA.read_text(encoding="utf-8"))
        cls.example = json.loads(LOCK_EXAMPLE.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)

    def test_example_is_v2_and_schema_valid(self) -> None:
        Draft202012Validator(self.schema).validate(self.example)
        self.assertEqual(self.example["schema_version"], 2)
        self.assertNotIn("recipe", self.example)
        self.assertEqual(self.example["intent"]["recipe"], "webapp")
        self.assertRegex(self.example["recipe_sha256"], r"^[0-9a-f]{64}$")

    def test_v1_shape_is_rejected(self) -> None:
        value = copy.deepcopy(self.example)
        value["schema_version"] = 1
        value["recipe"] = value.pop("intent")["recipe"]
        value.pop("recipe_sha256")
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.schema).validate(value)

    def test_reserved_transaction_and_staging_destinations_are_rejected(self) -> None:
        for destination in (
            ".template-composition/transaction.json",
            ".template-composition/staging",
            ".template-composition/staging/abc/material",
        ):
            value = copy.deepcopy(self.example)
            value["files"][0]["destination"] = destination
            value["files"] = sorted(value["files"], key=lambda entry: entry["destination"])
            with self.subTest(destination=destination):
                with self.assertRaises(ValidationError):
                    Draft202012Validator(self.schema).validate(value)

    def test_initial_apply_records_normalized_intent_and_recipe_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "composition.json"
            config_value = {
                "schema_version": 1,
                "recipe": "skill",
                "components": {
                    "include": ["capability.service", "capability.cli"],
                    "exclude": ["lifecycle.release-evidence"],
                },
                "parameters": {
                    "capability.service": {"z": 1, "a": {"z": 2, "a": 3}},
                    "capability.cli": {"format": "json"},
                },
            }
            config_path.write_text(json.dumps(config_value, indent=2) + "\n", encoding="utf-8")
            target = root / "consumer"
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
            lock = json.loads(
                (target / ".template-composition" / "lock.json").read_text(encoding="utf-8")
            )
            self.assertEqual(lock["schema_version"], 2)
            self.assertEqual(
                lock["intent"]["components"],
                {
                    "include": ["capability.cli", "capability.service"],
                    "exclude": ["lifecycle.release-evidence"],
                },
            )
            self.assertEqual(
                list(lock["intent"]["parameters"]),
                ["capability.cli", "capability.service"],
            )
            self.assertEqual(
                list(lock["intent"]["parameters"]["capability.service"]),
                ["a", "z"],
            )
            self.assertEqual(
                lock["configuration_sha256"],
                hashlib.sha256(config_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(
                lock["recipe_sha256"],
                hashlib.sha256((ROOT / "recipes" / "skill.json").read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
