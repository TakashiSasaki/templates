from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
WRITER = ROOT / "components/lifecycle.lifecycle-checkpoints/files/.template-composition/checkpoint.py"
spec = importlib.util.spec_from_file_location("checkpoint_writer", WRITER)
assert spec and spec.loader
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


class LifecycleCheckpointWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write(
            self.root / "contracts/manifest.json",
            {
                "contracts": [
                    {
                        "id": "implementation_evidence",
                        "document": "contracts/implementation-evidence.json",
                        "schema": "schemas/implementation-evidence.schema.json",
                    },
                    {
                        "id": "lifecycle_checkpoints",
                        "document": "contracts/lifecycle-checkpoints.json",
                        "schema": "schemas/lifecycle-checkpoints.schema.json",
                    },
                ]
            },
        )
        write(self.root / "contracts/implementation-evidence.json", {"mode": "planning", "requirements": []})
        write(
            self.root / "contracts/lifecycle-checkpoints.json",
            {
                "$schema": "../schemas/lifecycle-checkpoints.schema.json",
                "schemaVersion": 1,
                "checkpoints": [],
            },
        )
        write(self.root / "schemas/implementation-evidence.schema.json", {"type": "object"})
        write(self.root / "schemas/lifecycle-checkpoints.schema.json", {"type": "object"})
        validator = self.root / ".template-composition/validate.py"
        validator.parent.mkdir(parents=True, exist_ok=True)
        validator.write_text(
            "import json\nprint(json.dumps({'schema_version': 1, 'status': 'valid', 'checks': []}))\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_planning_checkpoint_accepts_canonical_valid_status(self) -> None:
        entry = writer.create_checkpoint(
            self.root,
            checkpoint_id="initial-planning",
            phase="planning",
            from_id=None,
            source_revision=None,
        )
        self.assertEqual(entry["phase"], "planning")
        ledger = json.loads((self.root / "contracts/lifecycle-checkpoints.json").read_text(encoding="utf-8"))
        self.assertEqual([item["id"] for item in ledger["checkpoints"]], ["initial-planning"])
        snapshot = self.root / entry["snapshotPath"]
        self.assertTrue((snapshot / "validation.json").is_file())
        self.assertTrue((snapshot / "contracts/implementation-evidence.json").is_file())
        self.assertTrue((snapshot / "schemas/lifecycle-checkpoints.schema.json").is_file())

    def test_checkpoint_fails_closed_when_prewrite_validation_is_invalid(self) -> None:
        validator = self.root / ".template-composition/validate.py"
        validator.write_text(
            "import json,sys\nprint(json.dumps({'schema_version': 1, 'status': 'invalid', 'checks': []}))\nsys.exit(1)\n",
            encoding="utf-8",
        )
        with self.assertRaises(writer.CheckpointError):
            writer.create_checkpoint(
                self.root,
                checkpoint_id="initial-planning",
                phase="planning",
                from_id=None,
                source_revision=None,
            )
        ledger = json.loads((self.root / "contracts/lifecycle-checkpoints.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger["checkpoints"], [])
        self.assertFalse((self.root / "artifacts/lifecycle/001-initial-planning").exists())

    def test_postwrite_validation_failure_rolls_back_ledger_and_snapshot(self) -> None:
        validator = self.root / ".template-composition/validate.py"
        validator.write_text(
            "from pathlib import Path\n"
            "import json,sys\n"
            "root=Path(sys.argv[1])\n"
            "ledger=json.loads((root/'contracts/lifecycle-checkpoints.json').read_text())\n"
            "valid=not ledger.get('checkpoints')\n"
            "print(json.dumps({'schema_version':1,'status':'valid' if valid else 'invalid','checks':[]}))\n"
            "raise SystemExit(0 if valid else 1)\n",
            encoding="utf-8",
        )
        with self.assertRaises(writer.CheckpointError):
            writer.create_checkpoint(
                self.root,
                checkpoint_id="initial-planning",
                phase="planning",
                from_id=None,
                source_revision=None,
            )
        ledger = json.loads((self.root / "contracts/lifecycle-checkpoints.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger["checkpoints"], [])
        self.assertFalse((self.root / "artifacts/lifecycle/001-initial-planning").exists())


if __name__ == "__main__":
    unittest.main()
