from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = (
    ROOT
    / "components"
    / "lifecycle.implementation-evidence"
    / "files"
    / ".template-composition"
    / "validators"
    / "validate_implementation_evidence.py"
)
COMMON_DIR = (
    ROOT
    / "components"
    / "lifecycle.contract-evolution"
    / "files"
    / ".template-composition"
    / "validators"
)

if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
SPEC = importlib.util.spec_from_file_location("implementation_evidence_validator", VALIDATOR)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load implementation evidence validator")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def proof(proof_id: str, *, expected: str = "shared result") -> dict:
    return {
        "id": proof_id,
        "status": "verified",
        "kind": "integration-test",
        "description": "Shared integration proof.",
        "locator": "tests/prove_everything.py",
        "commandId": "shared-proof",
        "expectedResult": expected,
    }


def record(record_id: str, contract_id: str, item_kind: str, item_id: str) -> dict:
    return {
        "id": record_id,
        "target": {
            "kind": "contract-item",
            "contractId": contract_id,
            "itemKind": item_kind,
            "itemId": item_id,
        },
        "implementationBoundary": {
            "status": "verified",
            "description": "Implemented.",
            "locator": f"product/{record_id}.py",
        },
        "positiveEvidence": [proof(f"{record_id}-positive")],
        "negativeEvidence": [
            proof(f"{record_id}-negative", expected=f"{record_id} rejects invalid state")
        ],
        "releaseGateIds": ["release"],
    }


class ImplementationEvidenceProofReuseTests(unittest.TestCase):
    def test_warns_for_exact_proof_reuse_across_three_target_families(self) -> None:
        records = [
            record("surface", "surfaces", "surface", "home"),
            record("route", "routes", "route", "home-route"),
            record("state", "ui_states", "state", "ready"),
        ]
        warnings = validator.proof_reuse_warnings(records)
        self.assertEqual(len(warnings), 1)
        warning = warnings[0]
        self.assertIn("3 target families", warning)
        self.assertIn("surfaces/surface", warning)
        self.assertIn("routes/route", warning)
        self.assertIn("ui_states/state", warning)
        self.assertIn("not invalid by itself", warning)

    def test_does_not_warn_for_many_items_within_one_target_family(self) -> None:
        records = [
            record("route-a", "routes", "route", "a"),
            record("route-b", "routes", "route", "b"),
            record("route-c", "routes", "route", "c"),
            record("route-d", "routes", "route", "d"),
        ]
        self.assertEqual(validator.proof_reuse_warnings(records), [])

    def test_different_expected_results_do_not_collapse_into_one_signature(self) -> None:
        records = [
            record("surface", "surfaces", "surface", "home"),
            record("route", "routes", "route", "home-route"),
            record("state", "ui_states", "state", "ready"),
        ]
        for index, entry in enumerate(records):
            entry["positiveEvidence"][0]["expectedResult"] = f"claim-specific result {index}"
        self.assertEqual(validator.proof_reuse_warnings(records), [])

    def test_cli_warning_is_non_fatal_and_machine_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contracts = root / "contracts"
            contracts.mkdir()
            records = [
                record("surface", "surfaces", "surface", "home"),
                record("route", "routes", "route", "home-route"),
                record("state", "ui_states", "state", "ready"),
            ]
            manifest = {
                "contracts": [
                    {"id": contract_id, "versionHistory": [{"version": 1}]}
                    for contract_id in ("routes", "surfaces", "ui_states")
                ]
            }
            evidence = {
                "mode": "product",
                "commands": [
                    {
                        "id": "shared-proof",
                        "command": "python tests/prove_everything.py",
                        "purpose": "Run shared product proof.",
                    }
                ],
                "releaseGates": [
                    {
                        "id": "release",
                        "purpose": "Run release proof.",
                        "commandIds": ["shared-proof"],
                    }
                ],
                "records": records,
            }
            (contracts / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            (contracts / "implementation-evidence.json").write_text(
                json.dumps(evidence), encoding="utf-8"
            )
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(COMMON_DIR)
            result = subprocess.run(
                [sys.executable, str(VALIDATOR), str(root)],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stderr, "")
            self.assertIn("WARNING: broad implementation-evidence proof reuse", result.stdout)
            self.assertIn("Implementation evidence validation: OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
