from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
WALKTHROUGH = ROOT / "docs" / "guides" / "webapp-product-walkthrough.md"
BROWSER_PROOF = (
    ROOT / "examples" / "onboarding" / "task-ledger" / "browser_proof.py"
)
EXAMPLE_CONFIG = ROOT / "examples" / "onboarding" / "task-ledger" / "composition.json"


class TaskLedgerWalkthroughBrowserAcceptanceTests(unittest.TestCase):
    def code_block(self, marker: str, language: str) -> str:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        marker_at = text.index(marker)
        opening = f"```{language}\n"
        start = text.index(opening, marker_at) + len(opening)
        end = text.index("\n```", start)
        return text[start:end] + "\n"

    def run_python(
        self, cwd: Path, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *arguments],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_json(self, path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def materialize(self, root: Path) -> Path:
        target = root / "task-ledger"
        result = self.run_python(
            ROOT,
            str(COMPOSER),
            "apply",
            "--config",
            str(EXAMPLE_CONFIG),
            "--target",
            str(target),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return target

    def specialize_browser_contracts(self, target: Path) -> None:
        routes_path = target / "contracts" / "routes.json"
        routes = json.loads(routes_path.read_text(encoding="utf-8"))
        routes["routes"][0]["states"] = ["ready", "empty", "error"]
        self.write_json(routes_path, routes)

        states_path = target / "contracts" / "ui-states.json"
        states = json.loads(states_path.read_text(encoding="utf-8"))
        ready = states["states"][0]
        ready["focusStrategy"] = "preserve"
        states["states"] = [
            ready,
            {
                "id": "empty",
                "scope": "route",
                "category": "content",
                "description": "The task list is empty and the empty message is visible.",
                "recoveryActions": [],
                "announcement": "polite",
                "focusStrategy": "preserve",
            },
            {
                "id": "error",
                "scope": "route",
                "category": "error",
                "description": "A task-list refresh failed and the visible status region reports the failure.",
                "recoveryActions": [],
                "announcement": "polite",
                "focusStrategy": "preserve",
            },
        ]
        self.write_json(states_path, states)

    def install_walkthrough_product(self, target: Path) -> None:
        (target / "task_ledger" / "static").mkdir(parents=True)
        (target / "tests").mkdir(exist_ok=True)
        (target / "scripts").mkdir(exist_ok=True)
        (target / "task_ledger" / "__init__.py").write_text("", encoding="utf-8")
        (target / "task_ledger" / "cli.py").write_text(
            self.code_block("Create `task_ledger/cli.py`:", "python"),
            encoding="utf-8",
        )
        (target / "task_ledger" / "static" / "index.html").write_text(
            self.code_block("Create `task_ledger/static/index.html`:", "html"),
            encoding="utf-8",
        )
        (target / "tests" / "test_task_ledger.py").write_text(
            self.code_block("Create `tests/test_task_ledger.py`:", "python"),
            encoding="utf-8",
        )
        (target / "tests" / "test_task_ledger_browser.py").write_text(
            BROWSER_PROOF.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        verifier = target / "scripts" / "verify.sh"
        verifier.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            "python -m unittest discover -s tests -p 'test_task_ledger.py' -v\n"
            "python tests/test_task_ledger_browser.py\n",
            encoding="utf-8",
        )
        verifier.chmod(0o755)

    def service_operations(self) -> list[dict[str, str]]:
        return [{'id': 'list-tasks', 'invocation': 'GET /api/tasks?status=all|open|completed', 'success': '200 JSON task array for a valid status filter', 'negative': '400 JSON error for an invalid status filter'}, {'id': 'get-task', 'invocation': 'GET /api/tasks/{id}', 'success': '200 JSON task for an existing id', 'negative': '404 JSON error for a missing id'}, {'id': 'create-task', 'invocation': 'POST /api/tasks', 'success': '201 JSON task for a non-empty title', 'negative': '400 JSON error for an empty title'}, {'id': 'update-task', 'invocation': 'PATCH /api/tasks/{id}', 'success': '200 JSON updated task for an existing id', 'negative': '404 JSON error for a missing id'}, {'id': 'delete-task', 'invocation': 'DELETE /api/tasks/{id}', 'success': '204 for an existing id', 'negative': '404 JSON error when the id no longer exists'}, {'id': 'health', 'invocation': 'GET /healthz', 'success': '200 JSON status ok', 'negative': '404 JSON error for an unknown service path'}]

    def productize_service_contract(self, target: Path) -> None:
        self.write_json(
            target / "contracts" / "service-interface.json",
            {
                "$schema": "../schemas/service-interface.schema.json",
                "schemaVersion": 1,
                "mode": "product",
                "protocol": "http-json",
                "operations": self.service_operations(),
            },
        )

    def productize_cli_contract(self, target: Path) -> None:
        self.write_json(
            target / "contracts" / "cli-interface.json",
            {
                "$schema": "../schemas/cli-interface.schema.json",
                "schemaVersion": 1,
                "mode": "product",
                "entrypoints": [
                    {
                        "id": "task-ledger",
                        "command": [
                            "python",
                            "-m",
                            "task_ledger.cli",
                            "--database",
                            "task-ledger.db",
                        ],
                        "workingDirectory": ".",
                        "helpArguments": ["--help"],
                        "versionArguments": ["--version"],
                        "structuredOutput": {
                            "arguments": ["export"],
                            "format": "json",
                            "contractVersionField": "contractVersion",
                        },
                        "exitCodes": {
                            "success": 0,
                            "negativeResult": 1,
                            "invalidInput": 2,
                            "unavailable": 3,
                            "refused": 4,
                            "internalFailure": 5,
                            "additionalInputRequired": 6,
                        },
                    }
                ],
            },
        )

    def expected_targets(self, target: Path) -> list[dict[str, str]]:
        surfaces = json.loads(
            (target / "contracts" / "surfaces.json").read_text(encoding="utf-8")
        )
        routes = json.loads(
            (target / "contracts" / "routes.json").read_text(encoding="utf-8")
        )
        states = json.loads(
            (target / "contracts" / "ui-states.json").read_text(encoding="utf-8")
        )
        viewports = json.loads(
            (target / "contracts" / "viewports.json").read_text(encoding="utf-8")
        )
        targets: list[dict[str, str]] = []
        for contract_id, item_kind, items, key in (
            ("surfaces", "surface", surfaces["surfaces"], "id"),
            ("routes", "route", routes["routes"], "id"),
            ("ui_states", "ui-state", states["states"], "id"),
            ("viewports", "viewport", viewports["viewports"], "id"),
        ):
            targets.extend(
                {
                    "kind": "contract-item",
                    "contractId": contract_id,
                    "itemKind": item_kind,
                    "itemId": item[key],
                }
                for item in items
            )
        targets.extend(
            {
                "kind": "contract-item",
                "contractId": "viewports",
                "itemKind": "input-capability",
                "itemId": item,
            }
            for item in viewports["inputCapabilities"]
        )
        return targets

    def productize_evidence(self, target: Path) -> None:
        records = []
        requirements = []
        for index, evidence_target in enumerate(self.expected_targets(target), 1):
            record_id = f"task-ledger-{index}"
            requirement_id = f"REQ-TASK-LEDGER-{index}"
            records.append(
                {
                    "id": record_id,
                    "target": evidence_target,
                    "implementationBoundary": {
                        "status": "verified",
                        "description": "Task Ledger browser implementation owns this target.",
                        "locator": "task_ledger/static/index.html",
                    },
                    "positiveEvidence": [
                        {
                            "id": f"{record_id}-positive",
                            "status": "verified",
                            "kind": "end-to-end-test",
                            "description": "Real Chrome executes the supported target path.",
                            "locator": "tests/test_task_ledger_browser.py",
                            "commandId": "verify-product",
                            "expectedResult": "The supported browser interaction passes.",
                        }
                    ],
                    "negativeEvidence": [
                        {
                            "id": f"{record_id}-negative",
                            "status": "verified",
                            "kind": "end-to-end-test",
                            "description": "Real Chrome rejects or excludes invalid behavior.",
                            "locator": "tests/test_task_ledger_browser.py",
                            "commandId": "verify-product",
                            "expectedResult": "The invalid browser behavior is absent or rejected.",
                        }
                    ],
                    "releaseGateIds": ["product-verification"],
                }
            )
            requirements.append(
                {
                    "id": requirement_id,
                    "description": (
                        "Task Ledger satisfies the declared "
                        f"{evidence_target['contractId']} {evidence_target['itemKind']} "
                        f"target {evidence_target['itemId']} through real browser behavior."
                    ),
                    "recordIds": [record_id],
                    "requiredPositiveProofKinds": ["end-to-end-test"],
                }
            )
        for operation in self.service_operations():
            operation_id = operation["id"]
            record_id = f"task-ledger-service-{operation_id}"
            records.append(
                {
                    "id": record_id,
                    "target": {
                        "kind": "contract-item",
                        "contractId": "service_interface",
                        "itemKind": "operation",
                        "itemId": operation_id,
                    },
                    "implementationBoundary": {
                        "status": "verified",
                        "description": "Task Ledger exposes this independently reachable HTTP service operation.",
                        "locator": "task_ledger/cli.py",
                    },
                    "positiveEvidence": [
                        {
                            "id": f"{record_id}-positive",
                            "status": "verified",
                            "kind": "integration-test",
                            "description": f"Execute the success path for {operation_id} through HTTP.",
                            "locator": "tests/test_task_ledger.py",
                            "commandId": "verify-product",
                            "expectedResult": operation["success"],
                        }
                    ],
                    "negativeEvidence": [
                        {
                            "id": f"{record_id}-negative",
                            "status": "verified",
                            "kind": "integration-test",
                            "description": f"Execute the negative path for {operation_id} through HTTP.",
                            "locator": "tests/test_task_ledger.py",
                            "commandId": "verify-product",
                            "expectedResult": operation["negative"],
                        }
                    ],
                    "releaseGateIds": ["product-verification"],
                }
            )
            requirements.append(
                {
                    "id": f"REQ-TASK-LEDGER-SERVICE-{operation_id.upper()}",
                    "description": f"Task Ledger service operation {operation_id} executes its documented success and negative behavior.",
                    "recordIds": [record_id],
                    "requiredPositiveProofKinds": ["integration-test"],
                }
            )

        cli_record_id = "task-ledger-cli"
        records.append(
            {
                "id": cli_record_id,
                "target": {
                    "kind": "contract-item",
                    "contractId": "cli_interface",
                    "itemKind": "entrypoint",
                    "itemId": "task-ledger",
                },
                "implementationBoundary": {
                    "status": "verified",
                    "description": "Task Ledger exposes the selected packaged CLI entrypoint.",
                    "locator": "task_ledger/cli.py",
                },
                "positiveEvidence": [
                    {
                        "id": "task-ledger-cli-positive",
                        "status": "verified",
                        "kind": "integration-test",
                        "description": "CLI help, version, and structured export execute successfully.",
                        "locator": "tests/test_task_ledger.py",
                        "commandId": "verify-product",
                        "expectedResult": "Help/version succeed and export emits contractVersion 1 JSON.",
                    }
                ],
                "negativeEvidence": [
                    {
                        "id": "task-ledger-cli-negative",
                        "status": "verified",
                        "kind": "integration-test",
                        "description": "CLI rejects an invalid status argument through argparse.",
                        "locator": "tests/test_task_ledger.py",
                        "commandId": "verify-product",
                        "expectedResult": "Invalid --status exits with code 2 and a diagnostic.",
                    }
                ],
                "releaseGateIds": ["product-verification"],
            }
        )
        requirements.append(
            {
                "id": "REQ-TASK-LEDGER-CLI",
                "description": "Task Ledger exposes a versioned structured CLI with executable positive and negative behavior.",
                "recordIds": [cli_record_id],
                "requiredPositiveProofKinds": ["integration-test"],
            }
        )

        self.write_json(
            target / "contracts" / "implementation-evidence.json",
            {
                "$schema": "../schemas/implementation-evidence.schema.json",
                "schemaVersion": 4,
                "mode": "product",
                "commands": [
                    {
                        "id": "verify-product",
                        "command": "./scripts/verify.sh",
                        "purpose": "Run unit, integration, and real-browser proof.",
                    }
                ],
                "releaseGates": [
                    {
                        "id": "product-verification",
                        "purpose": "Require the complete Task Ledger product proof.",
                        "commandIds": ["verify-product"],
                    }
                ],
                "requirements": requirements,
                "records": records,
            },
        )

    def test_walkthrough_reaches_real_browser_product_mode_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
            self.specialize_browser_contracts(target)
            self.install_walkthrough_product(target)

            unit = self.run_python(
                target,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_task_ledger.py",
                "-v",
            )
            self.assertEqual(unit.returncode, 0, unit.stdout + unit.stderr)

            browser = self.run_python(target, "tests/test_task_ledger_browser.py")
            self.assertEqual(browser.returncode, 0, browser.stdout + browser.stderr)
            self.assertIn("viewport and keyboard positive/negative paths passed", browser.stdout)

            self.productize_service_contract(target)
            self.productize_cli_contract(target)
            self.productize_evidence(target)
            validation = self.run_python(
                ROOT, str(COMPOSER), "validate", "--target", str(target)
            )
            self.assertEqual(
                validation.returncode,
                0,
                validation.stdout + validation.stderr,
            )
            payload = json.loads(validation.stdout)
            self.assertEqual(payload["status"], "valid")


if __name__ == "__main__":
    unittest.main()