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
spec = importlib.util.spec_from_file_location("checkpoint_validator", VALIDATOR)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def req(rid: str = "REQ-CLI", target: str = "main", contract: str = "cli_interface", kind: str = "entrypoint") -> dict:
    return {
        "id": rid,
        "description": f"Implement {rid}.",
        "targets": [{"kind": "contract-item", "contractId": contract, "itemKind": kind, "itemId": target}],
        "recordIds": [],
        "requiredPositiveProofKinds": ["integration-test"],
    }


def evidence(mode: str, requirements: list[dict]) -> dict:
    rendered = json.loads(json.dumps(requirements))
    if mode == "product":
        for item in rendered:
            item["recordIds"] = ["record-" + item["id"].lower()]
    return {
        "$schema": "../schemas/implementation-evidence.schema.json",
        "schemaVersion": 5,
        "mode": mode,
        "commands": [],
        "releaseGates": [],
        "records": [],
        "requirements": rendered,
    }


class LifecycleCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.manifest = {
            "contracts": [
                {"id": "implementation_evidence", "document": "contracts/implementation-evidence.json", "schema": "schemas/implementation-evidence.schema.json", "versionHistory": [{"version": 5}]},
                {"id": "cli_interface", "document": "contracts/cli-interface.json", "schema": "schemas/cli-interface.schema.json", "versionHistory": [{"version": 2}]},
                {"id": "mcp_interface", "document": "contracts/mcp-interface.json", "schema": "schemas/mcp-interface.schema.json", "versionHistory": [{"version": 2}]},
                {"id": "lifecycle_checkpoints", "document": "contracts/lifecycle-checkpoints.json", "schema": "schemas/lifecycle-checkpoints.schema.json", "versionHistory": [{"version": 1}]},
            ]
        }
        write(self.root / "contracts/manifest.json", self.manifest)
        write(self.root / "contracts/implementation-evidence.json", evidence("planning", [req()]))
        write(self.root / "contracts/cli-interface.json", {"schemaVersion": 2, "mode": "planning", "entrypoints": [{"id": "main"}]})
        write(self.root / "contracts/mcp-interface.json", {"schemaVersion": 2, "mode": "template", "transports": [], "operations": []})
        for name in ["implementation-evidence.schema.json", "cli-interface.schema.json", "mcp-interface.schema.json", "lifecycle-checkpoints.schema.json"]:
            write(self.root / "schemas" / name, {"type": "object"})
        self.ledger = {"$schema": "../schemas/lifecycle-checkpoints.schema.json", "schemaVersion": 1, "checkpoints": []}
        write(self.root / "contracts/lifecycle-checkpoints.json", self.ledger)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def checkpoint(self, cid: str, phase: str, change: str, parent: str | None) -> dict:
        sequence = len(self.ledger["checkpoints"]) + 1
        rel = f"artifacts/lifecycle/{sequence:03d}-{cid}"
        snap = self.root / rel
        paths = {"contracts/manifest.json"}
        for manifest_entry in self.manifest["contracts"]:
            if manifest_entry["id"] != "lifecycle_checkpoints":
                paths.update([manifest_entry["document"], manifest_entry["schema"]])
            else:
                paths.add(manifest_entry["schema"])
        files = []
        for path in sorted(paths):
            dest = snap / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.root / path, dest)
            files.append({"path": path, "snapshotPath": path, "sha256": digest(dest)})
        validation_result = {
            "schemaVersion": 1,
            "authority": "composition-selected-validation-v1",
            "command": ["python", ".template-composition/validate.py", ".", "--format", "json"],
            "result": "passed",
            "output": {"status": "valid"},
        }
        write(snap / "validation.json", validation_result)
        recorded_at = "2026-08-27T00:00:00Z"
        snapshot_manifest = {
            "schemaVersion": 1,
            "checkpointId": cid,
            "sequence": sequence,
            "phase": phase,
            "changeKind": change,
            "parentId": parent,
            "recordedAt": recorded_at,
            "chronologyAuthority": "sequence-parent-hash-chain",
            "authority": {"validationEntrypoint": ".template-composition/validate.py"},
            "files": files,
            "validation": {"result": "passed", "path": "validation.json", "sha256": digest(snap / "validation.json")},
        }
        write(snap / "manifest.json", snapshot_manifest)
        entry = {
            "id": cid,
            "sequence": sequence,
            "phase": phase,
            "changeKind": change,
            "parentId": parent,
            "snapshotPath": rel,
            "manifestSha256": digest(snap / "manifest.json"),
            "recordedAt": recorded_at,
        }
        self.ledger["checkpoints"].append(entry)
        write(self.root / "contracts/lifecycle-checkpoints.json", self.ledger)
        return entry

    def test_valid_planning_checkpoint_to_product_passes(self) -> None:
        self.checkpoint("initial-planning", "planning", "initial", None)
        write(self.root / "contracts/implementation-evidence.json", evidence("product", [req()]))
        self.assertEqual(validator.validate(self.root), [])

    def test_product_without_checkpoint_fails(self) -> None:
        write(self.root / "contracts/implementation-evidence.json", evidence("product", [req()]))
        errors = validator.validate(self.root)
        self.assertTrue(any("requires a validated planning checkpoint" in error for error in errors), errors)

    def test_planned_item_id_changed_before_product_fails(self) -> None:
        self.checkpoint("initial-planning", "planning", "initial", None)
        write(self.root / "contracts/implementation-evidence.json", evidence("product", [req(target="renamed")]))
        errors = validator.validate(self.root)
        self.assertTrue(any("changed planned requirement" in error for error in errors), errors)

    def test_checkpoint_content_modified_after_validation_fails(self) -> None:
        entry = self.checkpoint("initial-planning", "planning", "initial", None)
        path = self.root / entry["snapshotPath"] / "contracts/implementation-evidence.json"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        errors = validator.validate(self.root)
        self.assertTrue(any("snapshot hash mismatch" in error for error in errors), errors)

    def test_new_requirement_added_after_planning_baseline_fails(self) -> None:
        self.checkpoint("initial-planning", "planning", "initial", None)
        extra = req("REQ-MCP", "serve", "mcp_interface", "operation")
        write(self.root / "contracts/implementation-evidence.json", evidence("product", [req(), extra]))
        errors = validator.validate(self.root)
        self.assertTrue(any("added requirement" in error for error in errors), errors)

    def test_valid_specification_change_planning_checkpoint_passes(self) -> None:
        p1 = self.checkpoint("initial-planning", "planning", "initial", None)
        write(self.root / "contracts/implementation-evidence.json", evidence("product", [req()]))
        self.checkpoint("initial-product", "product", "initial", p1["id"])
        extra = req("REQ-MCP", "serve", "mcp_interface", "operation")
        write(self.root / "contracts/implementation-evidence.json", evidence("planning", [req(), extra]))
        self.checkpoint("category-change-planning", "planning", "specification-change", "initial-product")
        write(self.root / "contracts/implementation-evidence.json", evidence("product", [req(), extra]))
        self.assertEqual(validator.validate(self.root), [])

    def test_multiple_capability_targets_pass(self) -> None:
        extra = req("REQ-MCP", "serve", "mcp_interface", "operation")
        write(self.root / "contracts/implementation-evidence.json", evidence("planning", [req(), extra]))
        self.checkpoint("initial-planning", "planning", "initial", None)
        write(self.root / "contracts/implementation-evidence.json", evidence("product", [req(), extra]))
        self.assertEqual(validator.validate(self.root), [])

    def test_completed_product_checkpoint_detects_current_drift(self) -> None:
        p1 = self.checkpoint("initial-planning", "planning", "initial", None)
        write(self.root / "contracts/implementation-evidence.json", evidence("product", [req()]))
        self.checkpoint("initial-product", "product", "initial", p1["id"])
        changed = evidence("product", [req()])
        changed["requirements"][0]["description"] = "Changed after product checkpoint."
        write(self.root / "contracts/implementation-evidence.json", changed)
        errors = validator.validate(self.root)
        self.assertTrue(any("changed contracts/implementation-evidence.json after checkpoint" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
