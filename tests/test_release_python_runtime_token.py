from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


class ReleasePythonRuntimeTokenTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def materialize_release_consumer(self, root: Path) -> Path:
        target = root / "consumer"
        config = root / "composition.json"
        self.write_json(
            config,
            {
                "schema_version": 1,
                "recipe": "webapp",
                "components": {
                    "include": ["lifecycle.release-bundle"],
                    "exclude": [],
                },
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

    def run_release_execution_validator(
        self, target: Path
    ) -> subprocess.CompletedProcess[str]:
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

    def test_python_release_token_uses_producer_interpreter_not_path_lookup(self) -> None:
        from test_release_evidence_producer import ReleaseEvidenceProducerTests

        helper = ReleaseEvidenceProducerTests(
            methodName="test_success_produces_revision_bound_valid_evidence"
        )
        expected = sys.executable
        proof_script = (
            "import sys\n"
            f"expected = {expected!r}\n"
            "if sys.executable != expected:\n"
            "    raise SystemExit(23)\n"
            "print('managed Python runtime token used producer interpreter')\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision, _ = helper.materialize_candidate(
                Path(temp_dir), proof_script
            )
            result = helper.run_producer(target, revision)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "managed Python runtime token used producer interpreter",
            result.stdout,
        )

    def test_release_contract_rejects_host_specific_python_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_release_consumer(Path(temp_dir))
            self.write_json(
                target / "contracts/implementation-evidence.json",
                self.product_implementation(),
            )
            execution = self.product_execution()
            execution["commands"][0]["argv"][0] = sys.executable
            self.write_json(
                target / "contracts/release-execution.json",
                execution,
            )
            result = self.run_release_execution_validator(target)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("argv must exactly execute declared harness", result.stderr)


if __name__ == "__main__":
    unittest.main()
