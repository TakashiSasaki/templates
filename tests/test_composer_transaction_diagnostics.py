from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import composer_transaction as transaction  # noqa: E402

COMPOSER = ROOT / "scripts" / "compose.py"
CONSUMER_VALIDATOR = (
    ROOT
    / "components"
    / "lifecycle.composition-state"
    / "files"
    / ".template-composition"
    / "validate_composition.py"
)
TRANSACTION_RELATIVE = Path(".template-composition/transaction.json")
EXPECTED = "composition transaction is present; recovery required: .template-composition/transaction.json"


class ComposerTransactionDiagnosticTests(unittest.TestCase):
    def make_interrupted_target(self, root: Path) -> Path:
        target = root / "consumer"
        transaction_path = target / TRANSACTION_RELATIVE
        transaction_path.parent.mkdir(parents=True)
        transaction_path.write_text(
            json.dumps({"schema_version": 1, "operation": "upgrade"}) + "\n",
            encoding="utf-8",
        )
        return target

    @staticmethod
    def seed_file(destination: str, digest: str) -> dict:
        return {
            "destination": destination,
            "component": "capability.example",
            "ownership": "seed",
            "materialized_sha256": digest,
        }

    def test_inspect_uses_operation_neutral_transaction_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.make_interrupted_target(Path(temp_dir))
            result = subprocess.run(
                [sys.executable, str(COMPOSER), "inspect", "--target", str(target)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["state"], "managed-interrupted")
            self.assertEqual(payload["errors"], [EXPECTED])
            self.assertNotIn("update transaction", payload["errors"][0])

    def test_consumer_validator_uses_operation_neutral_transaction_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.make_interrupted_target(Path(temp_dir))
            result = subprocess.run(
                [sys.executable, str(CONSUMER_VALIDATOR), str(target)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(f"ERROR: {EXPECTED}", result.stderr)
            self.assertNotIn("update transaction", result.stderr)

    def test_shared_transaction_validator_uses_operation_neutral_seed_diagnostics(self) -> None:
        destination = "seed.txt"
        old = self.seed_file(destination, "1" * 64)
        new = self.seed_file(destination, "2" * 64)
        cases = (
            (
                {
                    "action": "replace",
                    "destination": destination,
                    "component": "capability.example",
                    "ownership": "seed",
                    "from_sha256": "1" * 64,
                    "to_sha256": "2" * 64,
                },
                {destination: old},
                {destination: new},
                "managed transaction cannot replace seed-owned material",
            ),
            (
                {
                    "action": "remove",
                    "destination": destination,
                    "component": "capability.example",
                    "ownership": "seed",
                    "from_sha256": "1" * 64,
                },
                {destination: old},
                {},
                "managed transaction cannot remove seed-owned material",
            ),
        )
        for action, old_files, new_files, expected in cases:
            with self.subTest(action=action["action"]):
                with self.assertRaises(transaction.TransactionError) as raised:
                    transaction._validate_action_against_locks(
                        action,
                        old_files,
                        new_files,
                    )
                self.assertEqual(raised.exception.code, "INVALID_TRANSACTION")
                self.assertIn(expected, raised.exception.message)
                self.assertNotIn("via update", raised.exception.message)


if __name__ == "__main__":
    unittest.main()
