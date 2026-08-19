from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
        transaction = target / TRANSACTION_RELATIVE
        transaction.parent.mkdir(parents=True)
        transaction.write_text(
            json.dumps({"schema_version": 1, "operation": "upgrade"}) + "\n",
            encoding="utf-8",
        )
        return target

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


if __name__ == "__main__":
    unittest.main()
