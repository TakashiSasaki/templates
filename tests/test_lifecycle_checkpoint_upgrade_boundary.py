from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "components/lifecycle.lifecycle-checkpoints/files/.template-composition/validators/validate_lifecycle_checkpoints.py"
COMMON = ROOT / "components/lifecycle.contract-evolution/files/.template-composition/validators"
if str(COMMON) not in sys.path:
    sys.path.insert(0, str(COMMON))
spec = importlib.util.spec_from_file_location("checkpoint_upgrade_validator", VALIDATOR)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LifecycleCheckpointUpgradeBoundaryTests(unittest.TestCase):
    def test_managed_schema_upgrade_does_not_become_product_specification_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract = {
                "$schema": "../schemas/implementation-evidence.schema.json",
                "schemaVersion": 5,
                "mode": "product",
                "commands": [],
                "releaseGates": [],
                "records": [],
                "requirements": [],
            }
            historical_manifest = {
                "contracts": [
                    {
                        "id": "implementation_evidence",
                        "document": "contracts/implementation-evidence.json",
                        "schema": "schemas/implementation-evidence.schema.json",
                        "versionHistory": [{"version": 5}],
                    },
                    {
                        "id": "lifecycle_checkpoints",
                        "document": "contracts/lifecycle-checkpoints.json",
                        "schema": "schemas/lifecycle-checkpoints.schema.json",
                        "versionHistory": [{"version": 1}],
                    },
                ]
            }
            write(root / "contracts/manifest.json", historical_manifest)
            write(root / "contracts/implementation-evidence.json", contract)
            write(root / "schemas/implementation-evidence.schema.json", {"managedVersion": 1})
            write(root / "schemas/lifecycle-checkpoints.schema.json", {"type": "object"})

            snapshot = root / "artifacts/lifecycle/001-initial-product"
            files = []
            for rel in (
                "contracts/manifest.json",
                "contracts/implementation-evidence.json",
                "schemas/implementation-evidence.schema.json",
            ):
                destination = snapshot / rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / rel, destination)
                files.append({"path": rel, "snapshotPath": rel, "sha256": sha(destination)})
            write(snapshot / "validation.json", {"result": "passed"})
            snapshot_manifest = {
                "schemaVersion": 1,
                "checkpointId": "initial-product",
                "sequence": 1,
                "phase": "planning",
                "changeKind": "initial",
                "parentId": None,
                "files": files,
                "validation": {
                    "result": "passed",
                    "path": "validation.json",
                    "sha256": sha(snapshot / "validation.json"),
                },
            }
            # The first entry must be planning. Make the current state planning too so
            # current-contract drift checks run while the managed schema changes.
            contract["mode"] = "planning"
            write(root / "contracts/implementation-evidence.json", contract)
            # Refresh the checkpointed contract to the same planning bytes.
            write(snapshot / "contracts/implementation-evidence.json", contract)
            for item in files:
                if item["path"] == "contracts/implementation-evidence.json":
                    item["sha256"] = sha(snapshot / item["path"])
            write(snapshot / "manifest.json", snapshot_manifest)
            ledger = {
                "$schema": "../schemas/lifecycle-checkpoints.schema.json",
                "schemaVersion": 1,
                "checkpoints": [
                    {
                        "id": "initial-product",
                        "sequence": 1,
                        "phase": "planning",
                        "changeKind": "initial",
                        "parentId": None,
                        "snapshotPath": "artifacts/lifecycle/001-initial-product",
                        "manifestSha256": sha(snapshot / "manifest.json"),
                        "recordedAt": "2026-08-27T00:00:00Z",
                    }
                ],
            }
            write(root / "contracts/lifecycle-checkpoints.json", ledger)

            # A Composition upgrade changes a managed schema, not the consumer's
            # specification contract. Historical snapshot integrity remains intact.
            write(root / "schemas/implementation-evidence.schema.json", {"managedVersion": 2})
            self.assertEqual(validator.validate(root), [])


if __name__ == "__main__":
    unittest.main()
