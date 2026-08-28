from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "components/lifecycle.release-execution"
RELEASE_FILES = RELEASE / "files"
ACTION_REGISTRY = RELEASE_FILES / ".template-composition/release-execution-actions.json"
ACTION_SCHEMA = RELEASE_FILES / ".template-composition/release-execution-actions.schema.json"
RESULT_SCHEMA = RELEASE_FILES / ".template-composition/release-candidate-verification.schema.json"
VERIFY_SCRIPT = RELEASE_FILES / ".template-composition/release/verify_candidate.py"
CANDIDATE_SCRIPT = RELEASE_FILES / ".template-composition/release/candidate.py"
RUN_ACTION = ROOT / "components/lifecycle.composition-state/files/.template-composition/run_action.py"


class ReleaseCandidateActionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(ACTION_REGISTRY.read_text(encoding="utf-8"))
        cls.action_schema = json.loads(ACTION_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.action_schema)
        cls.action_validator = Draft202012Validator(cls.action_schema)
        cls.action_validator.validate(cls.registry)

        cls.result_schema = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.result_schema)
        cls.result_validator = Draft202012Validator(cls.result_schema)

    def test_component_materializes_release_candidate_action(self) -> None:
        component = json.loads((RELEASE / "component.json").read_text(encoding="utf-8"))
        self.assertEqual(component["version"], 6)
        materials = {
            entry["destination"]: entry["ownership"]
            for entry in component["materials"]
        }
        for path in (
            ".template-composition/release-execution-actions.json",
            ".template-composition/release-execution-actions.schema.json",
            ".template-composition/release-candidate-verification.schema.json",
            ".template-composition/release/verify_candidate.py",
            ".template-composition/release/candidate.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(materials[path], "managed")

    def test_public_action_argv_is_exact_and_rejects_interpreter_augmentation(self) -> None:
        action = self.registry["actions"]["verify-release-candidate"]
        self.assertEqual(
            action,
            {
                "argv": [
                    "{python}",
                    ".template-composition/run_action.py",
                    "verify-release-candidate",
                    "{revision}",
                ],
                "caller_inputs": ["{python}", "{revision}"],
                "output_schema": ".template-composition/release-candidate-verification.schema.json",
            },
        )
        mutated = json.loads(json.dumps(self.registry))
        mutated["actions"]["verify-release-candidate"]["argv"].insert(1, "-I")
        with self.assertRaises(ValidationError):
            self.action_validator.validate(mutated)

    def _materialized_root(self, parent: Path) -> Path:
        root = parent / "consumer"
        release_dir = root / ".template-composition/release"
        release_dir.mkdir(parents=True)
        shutil.copy2(RUN_ACTION, root / ".template-composition/run_action.py")
        shutil.copy2(VERIFY_SCRIPT, release_dir / "verify_candidate.py")
        shutil.copy2(CANDIDATE_SCRIPT, release_dir / "candidate.py")
        return root

    def test_dispatcher_returns_structured_failure_when_git_candidate_prerequisite_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._materialized_root(Path(temp_dir))
            revision = "0" * 40
            result = subprocess.run(
                [
                    sys.executable,
                    str(root / ".template-composition/run_action.py"),
                    "verify-release-candidate",
                    revision,
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.result_validator.validate(payload)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["revision"], revision)
        self.assertIn(".git", payload["error"])

    def test_dispatcher_rejects_missing_revision_before_provider_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._materialized_root(Path(temp_dir))
            result = subprocess.run(
                [
                    sys.executable,
                    str(root / ".template-composition/run_action.py"),
                    "verify-release-candidate",
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("exactly one caller value", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
