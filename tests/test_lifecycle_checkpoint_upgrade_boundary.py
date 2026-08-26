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
                "mode": "planning",
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

            snapshot = root / "artifacts/lifecycle/001-initial-planning"
            files = []
            for rel in (
                "contracts/manifest.json",
                "contracts/implementation-evidence.json",
                "schemas/implementation-evidence.schema.json",
                "schemas/lifecycle-checkpoints.schema.json",
            ):
                destination = snapshot / rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / rel, destination)
                files.append({"path": rel, "snapshotPath": rel, "sha256": sha(destination)})
            validation_result = {
                "schemaVersion": 1,
                "authority": "composition-selected-validation-v1",
                "command": ["python", ".template-composition/validate.py", ".", "--format", "json"],
                "result": "passed",
                "output": {"status": "valid"},
            }
            write(snapshot / "validation.json", validation_result)
            recorded_at = "2026-08-27T00:00:00Z"
            snapshot_manifest = {
                "schemaVersion": 1,
                "checkpointId": "initial-planning",
                "sequence": 1,
                "phase": "planning",
                "changeKind": "initial",
                "parentId": None,
                "recordedAt": recorded_at,
                "chronologyAuthority": "sequence-parent-hash-chain",
                "authority": {"validationEntrypoint": ".template-composition/validate.py"},
                "files": files,
                "validation": {
                    "result": "passed",
                    "path": "validation.json",
                    "sha256": sha(snapshot / "validation.json"),
                },
            }
            write(snapshot / "manifest.json", snapshot_manifest)
            ledger = {
                "$schema": "../schemas/lifecycle-checkpoints.schema.json",
                "schemaVersion": 1,
                "checkpoints": [
                    {
                        "id": "initial-planning",
                        "sequence": 1,
                        "phase": "planning",
                        "changeKind": "initial",
                        "parentId": None,
                        "snapshotPath": "artifacts/lifecycle/001-initial-planning",
                        "manifestSha256": sha(snapshot / "manifest.json"),
                        "recordedAt": recorded_at,
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
