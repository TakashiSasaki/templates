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
import composer_upgrade as upgrade  # noqa: E402


class ComposerPublicRecoveryModeMismatchAcceptanceTests(unittest.TestCase):
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

    def write_config(self, path: Path, *, include: list[str] | None = None) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "recipe": "skill",
                    "components": {"include": include or [], "exclude": []},
                    "parameters": {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def materialize_initial(self, root: Path) -> Path:
        config_path = root / "initial.json"
        self.write_config(config_path)
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

    def build_update_marker(self, target: Path) -> tuple[Path, bytes]:
        destination = "docs/architecture.md"
        material_path = target / destination
        previous = b"synthetic previous managed bytes for mode mismatch acceptance\n"
        self.assertNotEqual(material_path.read_bytes(), previous)
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
        marker = transaction._build_transaction(
            target,
            plan,
            old_lock_bytes,
            json.loads(old_lock_bytes),
        )
        marker_path = target / core.TRANSACTION_RELATIVE
        marker_bytes = transaction._transaction_bytes(marker)
        transaction._write_no_overwrite_durable(target, marker_path, marker_bytes)
        return material_path, marker_bytes

    def build_upgrade_marker(self, target: Path, config_path: Path) -> bytes:
        old_lock_path = target / core.LOCK_RELATIVE
        old_lock_bytes = old_lock_path.read_bytes()
        status, plan = upgrade.plan_upgrade(target, config_path)
        self.assertEqual(status, 0, plan)
        self.assertEqual(plan["conflicts"], [])
        marker = upgrade._build_upgrade_transaction(
            plan,
            old_lock_bytes,
            json.loads(old_lock_bytes),
        )
        marker_bytes = transaction._transaction_bytes(marker)
        transaction._write_no_overwrite_durable(
            target,
            target / core.TRANSACTION_RELATIVE,
            marker_bytes,
        )
        return marker_bytes

    def assert_interrupted(self, target: Path) -> None:
        result, payload = self.run_composer("inspect", "--target", str(target))
        self.assertEqual(result.returncode, 2, payload)
        self.assertEqual(payload["state"], "managed-interrupted")

    def assert_operation_mismatch(self, result: subprocess.CompletedProcess[str], payload: dict) -> None:
        self.assertEqual(result.returncode, 2, payload)
        self.assertEqual(payload["code"], "RECOVERY_OPERATION_MISMATCH")
        self.assertIn("operation recorded", payload["message"])

    def test_update_transaction_rejects_upgrade_recovery_mode_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_initial(Path(temp_dir))
            material_path, marker_bytes = self.build_update_marker(target)
            material_before = material_path.read_bytes()
            marker_path = target / core.TRANSACTION_RELATIVE
            self.assert_interrupted(target)

            result, payload = self.run_composer(
                "apply",
                "--mode",
                "upgrade",
                "--target",
                str(target),
            )
            self.assert_operation_mismatch(result, payload)
            self.assertEqual(material_path.read_bytes(), material_before)
            self.assertEqual(marker_path.read_bytes(), marker_bytes)
            self.assert_interrupted(target)

    def test_upgrade_transaction_rejects_update_recovery_mode_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = self.materialize_initial(root)
            upgrade_config = root / "upgrade.json"
            self.write_config(upgrade_config, include=["capability.cli"])
            marker_bytes = self.build_upgrade_marker(target, upgrade_config)
            marker_path = target / core.TRANSACTION_RELATIVE
            self.assertFalse((target / "CLI_INTERFACE.md").exists())
            self.assert_interrupted(target)

            result, payload = self.run_composer(
                "apply",
                "--mode",
                "update",
                "--target",
                str(target),
            )
            self.assert_operation_mismatch(result, payload)
            self.assertFalse((target / "CLI_INTERFACE.md").exists())
            self.assertEqual(marker_path.read_bytes(), marker_bytes)
            self.assert_interrupted(target)


if __name__ == "__main__":
    unittest.main()
