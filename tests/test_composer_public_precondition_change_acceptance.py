from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
COMPOSER = SCRIPTS / "compose.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_core as core  # noqa: E402
import composer_managed as managed  # noqa: E402
import composer_transaction as transaction  # noqa: E402


class ComposerPublicPreconditionChangeAcceptanceTests(unittest.TestCase):
    def run_composer(self, *arguments: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [sys.executable, str(COMPOSER), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"composer did not emit JSON: {exc}\n{result.stdout}\n{result.stderr}")
        return result, payload

    def materialize_initial(self, root: Path) -> Path:
        config_path = root / "composition.json"
        config_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "recipe": "skill",
                    "components": {"include": [], "exclude": []},
                    "parameters": {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        target = root / "consumer"
        result, payload = self.run_composer(
            "apply",
            "--config",
            str(config_path),
            "--target",
            str(target),
        )
        self.assertEqual(result.returncode, 0, payload)
        return target

    def start_replacement_transaction(self, target: Path) -> str:
        destination = "docs/architecture.md"
        material_path = target / destination
        desired = material_path.read_bytes()
        previous = b"synthetic previous managed bytes for precondition acceptance\n"
        self.assertNotEqual(previous, desired)

        material_path.write_bytes(previous)
        lock_path = target / core.LOCK_RELATIVE
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        entry = next(item for item in lock["files"] if item["destination"] == destination)
        self.assertEqual(entry["ownership"], "managed")
        entry["materialized_sha256"] = core.sha256_bytes(previous)
        lock_path.write_bytes(transaction._lock_bytes(lock))

        old_lock_bytes = lock_path.read_bytes()
        status, plan = managed.plan_update(target)
        self.assertEqual(status, 0, plan)
        self.assertIn(destination, {item["destination"] for item in plan["files"]["replace"]})

        old_lock = json.loads(old_lock_bytes)
        marker = transaction._build_transaction(target, plan, old_lock_bytes, old_lock)
        transaction._write_no_overwrite_durable(
            target,
            target / core.TRANSACTION_RELATIVE,
            transaction._transaction_bytes(marker),
        )
        return destination

    def test_public_update_recovery_preserves_third_state_and_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_initial(Path(temp_dir))
            destination = self.start_replacement_transaction(target)
            marker_path = target / core.TRANSACTION_RELATIVE
            material_path = target / destination
            third_state = b"consumer changed managed file after transaction start\n"
            material_path.write_bytes(third_state)

            result, interrupted = self.run_composer("inspect", "--target", str(target))
            self.assertEqual(result.returncode, 2, interrupted)
            self.assertEqual(interrupted["state"], "managed-interrupted")
            self.assertTrue(marker_path.is_file())

            result, failed = self.run_composer(
                "apply",
                "--mode",
                "update",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 2, failed)
            self.assertEqual(failed["code"], "PRECONDITION_CHANGED")
            self.assertIn("will not force an overwrite", failed["message"])
            self.assertEqual(material_path.read_bytes(), third_state)
            self.assertTrue(marker_path.is_file())

            result, still_interrupted = self.run_composer("inspect", "--target", str(target))
            self.assertEqual(result.returncode, 2, still_interrupted)
            self.assertEqual(still_interrupted["state"], "managed-interrupted")
            self.assertEqual(material_path.read_bytes(), third_state)
            self.assertTrue(marker_path.is_file())


if __name__ == "__main__":
    unittest.main()
