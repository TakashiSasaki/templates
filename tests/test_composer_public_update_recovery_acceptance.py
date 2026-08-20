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


class ComposerPublicUpdateRecoveryAcceptanceTests(unittest.TestCase):
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

    def interrupt_update_after_one_replacement(self, target: Path) -> tuple[str, bytes]:
        destination = "docs/architecture.md"
        material_path = target / destination
        desired = material_path.read_bytes()
        previous = b"synthetic previous managed bytes for recovery acceptance\n"
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
        replacements = {item["destination"] for item in plan["files"]["replace"]}
        self.assertIn(destination, replacements)

        old_lock = json.loads(old_lock_bytes)
        marker = transaction._build_transaction(target, plan, old_lock_bytes, old_lock)
        marker_bytes = transaction._transaction_bytes(marker)
        transaction._write_no_overwrite_durable(
            target,
            target / core.TRANSACTION_RELATIVE,
            marker_bytes,
        )

        # Simulate interruption after the managed replacement reached its new bytes
        # but before the transaction completed and removed its durable marker.
        material_path.write_bytes(desired)
        return destination, desired

    def test_documented_public_update_recovery_rolls_forward_to_managed_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_initial(Path(temp_dir))
            destination, desired = self.interrupt_update_after_one_replacement(target)
            marker_path = target / core.TRANSACTION_RELATIVE
            self.assertTrue(marker_path.is_file())

            result, interrupted = self.run_composer("inspect", "--target", str(target))
            self.assertEqual(result.returncode, 2, interrupted)
            self.assertEqual(interrupted["state"], "managed-interrupted")
            self.assertTrue(interrupted["errors"])
            self.assertIn("recovery required", interrupted["errors"][0])
            self.assertTrue(marker_path.is_file(), "inspect must not mutate recovery state")

            result, recovered = self.run_composer(
                "apply",
                "--mode",
                "update",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, recovered)
            self.assertEqual(recovered["status"], "updated")
            self.assertTrue(recovered["recovered"])
            self.assertIn(destination, recovered["resumed"])
            self.assertFalse(marker_path.exists())
            self.assertEqual((target / destination).read_bytes(), desired)

            result, validated = self.run_composer("validate", "--target", str(target))
            self.assertEqual(result.returncode, 0, validated)
            self.assertEqual(validated["status"], "valid")
            self.assertEqual(validated["errors"], [])

            result, final_state = self.run_composer("inspect", "--target", str(target))
            self.assertEqual(result.returncode, 0, final_state)
            self.assertEqual(final_state["state"], "managed-valid")
            self.assertEqual(final_state["errors"], [])


if __name__ == "__main__":
    unittest.main()
