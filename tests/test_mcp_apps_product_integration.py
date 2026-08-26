from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import test_mcp_apps_contract as apps_helpers
import test_mcp_interface_contract as mcp_helpers
from executable_proof_test_support import (
    materialize_declared_harnesses,
    upgrade_product_evidence_v6,
)
from lifecycle_checkpoint_test_support import (
    create_planning_checkpoint,
    planning_evidence_from_product,
)

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


class McpAppsProductIntegrationTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def combined_product_evidence(self) -> dict:
        mcp_case = mcp_helpers.McpInterfaceContractTests(
            methodName="test_transport_and_operation_require_executable_positive_negative_proof"
        )
        apps_case = apps_helpers.McpAppsContractTests(
            methodName="test_product_apps_requires_target_specific_proof_strength"
        )
        evidence = deepcopy(
            mcp_case.evidence(
                proof_kind="end-to-end-test",
                requirement_kind="end-to-end-test",
            )
        )
        apps = deepcopy(apps_case.evidence())

        apps_command_id = "mcp-apps-proof"
        apps_gate_id = "mcp-apps-release"
        evidence["commands"].append(
            {
                "id": apps_command_id,
                "command": "python -m unittest tests.test_mcp_apps_runtime",
                "purpose": "Exercise MCP Apps extension, rendered View, and tool-to-View routing.",
            }
        )
        evidence["releaseGates"].append(
            {
                "id": apps_gate_id,
                "purpose": "Run MCP Apps protocol/browser/end-to-end proof.",
                "commandIds": [apps_command_id],
            }
        )

        for requirement in apps["requirements"]:
            requirement["id"] = requirement["id"].replace("_", "-")
            requirement["description"] = (
                "The declared MCP Apps target is caller-visible through the required "
                "protocol/browser execution boundary."
            )
        for record in apps["records"]:
            record["releaseGateIds"] = [apps_gate_id]
            for field, expected in (
                ("positiveEvidence", "documented MCP Apps success behavior"),
                ("negativeEvidence", "documented MCP Apps failure/degradation behavior"),
            ):
                proof = record[field][0]
                proof["description"] = "Execute the declared MCP Apps behavior through its required boundary."
                proof["locator"] = "tests/test_mcp_apps_runtime.py"
                proof["commandId"] = apps_command_id
                proof["expectedResult"] = expected

        evidence["requirements"].extend(apps["requirements"])
        evidence["records"].extend(apps["records"])
        return upgrade_product_evidence_v6(
            evidence,
            browser_command_ids={apps_command_id},
            harness_by_command={
                "mcp-proof": "tests/test_mcp_contract.py",
                apps_command_id: "tests/test_mcp_apps_runtime.py",
            },
        )

    def test_product_apps_passes_complete_selected_validation_chain(self) -> None:
        mcp_case = mcp_helpers.McpInterfaceContractTests(
            methodName="test_transport_and_operation_require_executable_positive_negative_proof"
        )
        apps_case = apps_helpers.McpAppsContractTests(
            methodName="test_product_apps_requires_target_specific_proof_strength"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config = root / "composition.json"
            self.write_json(
                config,
                {
                    "schema_version": 1,
                    "recipe": "skill",
                    "components": {
                        "include": ["capability.mcp-apps"],
                        "exclude": [],
                    },
                    "parameters": {},
                },
            )
            applied = subprocess.run(
                [
                    sys.executable,
                    str(COMPOSER),
                    "apply",
                    "--config",
                    str(config),
                    "--target",
                    str(target),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)

            product_evidence, planning_evidence = planning_evidence_from_product(
                self.combined_product_evidence()
            )
            self.write_json(
                target / "contracts/mcp-interface.json",
                {
                    "$schema": "../schemas/mcp-interface.schema.json",
                    "schemaVersion": 2,
                    "mode": "planning",
                    "protocolRevision": "2026-07-28",
                    "transports": [
                        {
                            "id": "stdio",
                            "kind": "stdio",
                            "purpose": "Expose the local MCP transport.",
                        }
                    ],
                    "operations": [
                        {
                            "id": "stdio-list-records",
                            "kind": "tool",
                            "transportId": "stdio",
                            "purpose": "Expose records.list through MCP.",
                        }
                    ],
                },
            )
            product_apps = apps_case.apps_contract()
            product_extension = product_apps["extension"]
            self.write_json(
                target / "contracts/mcp-apps.json",
                {
                    "$schema": "../schemas/mcp-apps.schema.json",
                    "schemaVersion": 2,
                    "mode": "planning",
                    "extension": {
                        "id": product_extension["id"],
                        "identifier": product_extension["identifier"],
                        "revision": product_extension["revision"],
                    },
                    "views": [
                        {"id": view["id"], "purpose": "Render the declared MCP App View."}
                        for view in product_apps["views"]
                    ],
                    "associations": [
                        {
                            "id": association["id"],
                            "operationId": association["operationId"],
                            "viewId": association["viewId"],
                            "purpose": "Bind the declared MCP operation to its View.",
                        }
                        for association in product_apps["associations"]
                    ],
                },
            )
            self.write_json(
                target / "contracts/implementation-evidence.json",
                planning_evidence,
            )
            create_planning_checkpoint(target)

            self.write_json(
                target / "contracts/mcp-interface.json",
                mcp_case.product_contract(),
            )
            self.write_json(
                target / "contracts/mcp-apps.json",
                product_apps,
            )
            self.write_json(
                target / "contracts/implementation-evidence.json",
                product_evidence,
            )
            materialize_declared_harnesses(target, product_evidence)

            runner = target / ".template-composition" / "validate.py"
            validated = subprocess.run(
                [sys.executable, str(runner), str(target), "--format", "json"],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            try:
                payload = json.loads(validated.stdout)
            except json.JSONDecodeError as exc:
                self.fail(
                    f"consumer validator did not emit JSON: {exc}\n"
                    f"stdout={validated.stdout}\nstderr={validated.stderr}"
                )
            self.assertEqual(validated.returncode, 0, payload)
            self.assertEqual(payload["status"], "valid")
            checks = {check["id"]: check for check in payload["checks"]}
            for check_id in (
                "contract-evolution",
                "implementation-evidence",
                "lifecycle-checkpoints",
                "mcp-interface",
                "mcp-apps",
            ):
                self.assertEqual(checks[check_id]["status"], "passed", checks[check_id])


if __name__ == "__main__":
    unittest.main()
