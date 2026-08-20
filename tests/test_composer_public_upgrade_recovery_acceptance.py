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
import composer_transaction as transaction  # noqa: E402
import composer_upgrade as upgrade  # noqa: E402


class ComposerPublicUpgradeRecoveryAcceptanceTests(unittest.TestCase):
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

    def interrupt_upgrade_after_one_create(self, target: Path, config_path: Path) -> tuple[str, bytes]:
        old_lock_path = target / core.LOCK_RELATIVE
        old_lock_bytes = old_lock_path.read_bytes()
        status, plan = upgrade.plan_upgrade(target, config_path)
        self.assertEqual(status, 0, plan)
        self.assertEqual(plan["conflicts"], [])

        old_lock = json.loads(old_lock_bytes)
        marker = upgrade._build_upgrade_transaction(plan, old_lock_bytes, old_lock)
        marker_bytes = transaction._transaction_bytes(marker)
        transaction._write_no_overwrite_durable(
            target,
            target / core.TRANSACTION_RELATIVE,
            marker_bytes,
        )

        material_map = upgrade._desired_materials_for_upgrade_transaction(marker)
        create_action = next(entry for entry in marker["actions"] if entry["action"] == "create")
        destination = create_action["destination"]
        material = material_map[destination]
        transaction._create_expected(
            target,
            target / destination,
            material.data,
            expected_sha256=create_action["to_sha256"],
        )
        return destination, material.data

    def test_documented_public_upgrade_recovery_rolls_forward_to_managed_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = self.materialize_initial(root)
            upgrade_config = root / "upgrade.json"
            self.write_config(upgrade_config, include=["capability.cli"])
            destination, desired = self.interrupt_upgrade_after_one_create(target, upgrade_config)
            marker_path = target / core.TRANSACTION_RELATIVE
            self.assertTrue(marker_path.is_file())
            self.assertEqual((target / destination).read_bytes(), desired)

            result, interrupted = self.run_composer("inspect", "--target", str(target))
            self.assertEqual(result.returncode, 2, interrupted)
            self.assertEqual(interrupted["state"], "managed-interrupted")
            self.assertTrue(interrupted["errors"])
            self.assertIn("recovery required", interrupted["errors"][0])
            self.assertTrue(marker_path.is_file(), "inspect must not mutate recovery state")

            result, recovered = self.run_composer(
                "apply",
                "--mode",
                "upgrade",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, recovered)
            self.assertEqual(recovered["status"], "upgraded")
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

            lock = json.loads((target / core.LOCK_RELATIVE).read_text(encoding="utf-8"))
            self.assertEqual(lock["intent"]["components"]["include"], ["capability.cli"])


if __name__ == "__main__":
    unittest.main()
