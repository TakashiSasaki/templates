from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lifecycle_checkpoint_test_support import create_planning_checkpoint

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
WALKTHROUGH = ROOT / "docs" / "guides" / "webapp-product-walkthrough.md"
BROWSER_PROOF = (
    ROOT / "examples" / "onboarding" / "task-ledger" / "browser_proof.py"
)
BROWSER_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "webapp_browser"
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
        application_routes_path = target / "contracts" / "application-routes.json"
        application_routes = json.loads(
            application_routes_path.read_text(encoding="utf-8")
        )
        application_routes["routes"][0]["states"] = ["ready", "empty", "error"]
        self.write_json(application_routes_path, application_routes)

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

    def specialize_walkthrough_browser_identity(self, target: Path) -> None:
        """Add the current Webapp browser-identity requirement to the acceptance product."""
        cli_path = target / "task_ledger" / "cli.py"
        cli_source = cli_path.read_text(encoding="utf-8")
        route_anchor = '''            if parsed.path == "/":
                body = (static_root / "index.html").read_bytes()
'''
        favicon_route = '''            if parsed.path == "/favicon.svg":
                body = (static_root / "favicon.svg").read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/":
                body = (static_root / "index.html").read_bytes()
'''
        self.assertEqual(cli_source.count(route_anchor), 1)
        cli_path.write_text(
            cli_source.replace(route_anchor, favicon_route),
            encoding="utf-8",
        )

        html_path = target / "task_ledger" / "static" / "index.html"
        html_source = html_path.read_text(encoding="utf-8")
        html_anchor = '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        self.assertEqual(html_source.count(html_anchor), 1)
        html_path.write_text(
            html_source.replace(
                html_anchor,
                html_anchor
                + '<link rel="icon" href="favicon.svg" type="image/svg+xml" sizes="any">\n',
            ),
            encoding="utf-8",
        )
        (target / "task_ledger" / "static" / "favicon.svg").write_text(
            (BROWSER_FIXTURE_DIR / "favicon.svg").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        proof_path = target / "tests" / "test_task_ledger_browser.py"
        proof_source = proof_path.read_text(encoding="utf-8")
        proof_anchor = '''        browser.navigate(base_url)
        layout = browser.execute(
'''
        identity_probe = '''        browser.navigate(base_url)
        favicon = json.loads(
            (PRODUCT_ROOT / "contracts" / "browser-identity.json").read_text(
                encoding="utf-8"
            )
        )["favicon"]
        identity = browser.execute(
            """
            const links = Array.from(document.querySelectorAll('link[rel]')).map((link) => ({
              relTokens: link.getAttribute('rel').trim().toLowerCase().split(/\\s+/),
              rawHref: link.getAttribute('href'),
              resolvedHref: link.href,
              mediaType: link.getAttribute('type') || '',
              sizes: link.sizes ? Array.from(link.sizes) : [],
            }));
            return {
              shortcutCount: links.filter((item) => item.relTokens.includes('shortcut')).length,
              iconLinks: links.filter((item) => item.relTokens.includes('icon')),
            };
            """
        )
        require(identity["shortcutCount"] == 0, "obsolete shortcut icon relation is present")
        primary = next(
            (
                item
                for item in identity["iconLinks"]
                if item["rawHref"] == favicon["href"]
            ),
            None,
        )
        require(primary is not None, "declared favicon link is missing")
        require(primary["relTokens"] == ["icon"], "favicon does not use standard rel=icon")
        require(primary["mediaType"] == favicon["mediaType"], "favicon media type drift")
        require(primary["sizes"] == favicon["sizes"], "favicon sizes drift")
        browser.navigate(primary["resolvedHref"])
        asset = browser.execute(
            """
            return {
              contentType: document.contentType,
              rootName: document.documentElement ? document.documentElement.localName : null,
            };
            """
        )
        require(
            asset == {"contentType": "image/svg+xml", "rootName": "svg"},
            "declared SVG favicon is not browser-retrievable as SVG",
        )
        print("Task Ledger browser identity proof: standard favicon linkage and asset retrieval passed")
        browser.navigate(base_url)
        layout = browser.execute(
'''
        self.assertEqual(proof_source.count(proof_anchor), 1)
        proof_path.write_text(
            proof_source.replace(proof_anchor, identity_probe),
            encoding="utf-8",
        )

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
        self.specialize_walkthrough_browser_identity(target)
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
        return [
            {"id": "list-tasks", "invocation": "GET /api/tasks?status=all|open|completed", "success": "200 JSON task array for a valid status filter", "negative": "400 JSON error for an invalid status filter"},
            {"id": "get-task", "invocation": "GET /api/tasks/{id}", "success": "200 JSON task for an existing id", "negative": "404 JSON error for a missing id"},
            {"id": "create-task", "invocation": "POST /api/tasks", "success": "201 JSON task for a non-empty title", "negative": "400 JSON error for an empty title"},
            {"id": "update-task", "invocation": "PATCH /api/tasks/{id}", "success": "200 JSON updated task for an existing id", "negative": "404 JSON error for a missing id"},
            {"id": "delete-task", "invocation": "DELETE /api/tasks/{id}", "success": "204 for an existing id", "negative": "404 JSON error when the id no longer exists"},
            {"id": "health", "invocation": "GET /healthz", "success": "200 JSON status ok", "negative": "404 JSON error for an unknown service path"},
        ]

    def productize_service_contract(self, target: Path) -> None:
        self.write_json(
            target / "contracts" / "service-interface.json",
            {
                "$schema": "../schemas/service-interface.schema.json",
                "schemaVersion": 2,
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
                "schemaVersion": 2,
                "mode": "product",
                "entrypoints": [
                    {
                        "id": "task-ledger",
                        "command": ["python", "-m", "task_ledger.cli", "--database", "task-ledger.db"],
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

    def webapp_evidence_helper(self, target: Path):
        helper_path = target / "scripts" / "webapp_evidence_targets.py"
        spec = importlib.util.spec_from_file_location(
            "_task_ledger_webapp_evidence_targets", helper_path
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader if spec is not None else None)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def expected_targets(self, target: Path) -> list[dict[str, str]]:
        helper = self.webapp_evidence_helper(target)
        return [dict(item) for item in helper.expected_targets(target)]

    def browser_requirement(
        self, index: int, target: dict[str, str], *, record_ids: list[str]
    ) -> dict:
        return {
            "id": f"REQ-TASK-LEDGER-{index}",
            "description": (
                "Task Ledger satisfies the declared "
                f"{target['contractId']} {target['itemKind']} "
                f"target {target['itemId']} through real browser behavior."
            ),
            "targets": [target],
            "recordIds": record_ids,
            "requiredPositiveProofKinds": ["end-to-end-test"],
        }

    def service_requirement(self, operation_id: str, *, record_ids: list[str]) -> dict:
        target = {
            "kind": "contract-item",
            "contractId": "service_interface",
            "itemKind": "operation",
            "itemId": operation_id,
        }
        return {
            "id": f"REQ-TASK-LEDGER-SERVICE-{operation_id.upper()}",
            "description": f"Task Ledger service operation {operation_id} executes its documented success and negative behavior.",
            "targets": [target],
            "recordIds": record_ids,
            "requiredPositiveProofKinds": ["integration-test"],
        }

    def cli_requirement(self, *, record_ids: list[str]) -> dict:
        return {
            "id": "REQ-TASK-LEDGER-CLI",
            "description": "Task Ledger exposes a versioned structured CLI with executable positive and negative behavior.",
            "targets": [
                {
                    "kind": "contract-item",
                    "contractId": "cli_interface",
                    "itemKind": "entrypoint",
                    "itemId": "task-ledger",
                }
            ],
            "recordIds": record_ids,
            "requiredPositiveProofKinds": ["integration-test"],
        }

    def prepare_planning_checkpoint(self, target: Path) -> None:
        self.write_json(
            target / "contracts" / "service-interface.json",
            {
                "$schema": "../schemas/service-interface.schema.json",
                "schemaVersion": 2,
                "mode": "planning",
                "protocol": "http-json",
                "operations": [
                    {
                        "id": operation["id"],
                        "purpose": f"Plan Task Ledger service operation {operation['id']}.",
                    }
                    for operation in self.service_operations()
                ],
            },
        )
        self.write_json(
            target / "contracts" / "cli-interface.json",
            {
                "$schema": "../schemas/cli-interface.schema.json",
                "schemaVersion": 2,
                "mode": "planning",
                "entrypoints": [
                    {
                        "id": "task-ledger",
                        "purpose": "Expose the Task Ledger command-line interface.",
                    }
                ],
            },
        )
        requirements = [
            self.browser_requirement(index, evidence_target, record_ids=[])
            for index, evidence_target in enumerate(self.expected_targets(target), 1)
        ]
        requirements.extend(
            self.service_requirement(operation["id"], record_ids=[])
            for operation in self.service_operations()
        )
        requirements.append(self.cli_requirement(record_ids=[]))
        self.write_json(
            target / "contracts" / "implementation-evidence.json",
            {
                "$schema": "../schemas/implementation-evidence.schema.json",
                "schemaVersion": 6,
                "mode": "planning",
                "commands": [],
                "releaseGates": [],
                "requirements": requirements,
                "records": [],
            },
        )
        create_planning_checkpoint(target)

    def productize_evidence(self, target: Path) -> None:
        records = []
        requirements = []
        for index, evidence_target in enumerate(self.expected_targets(target), 1):
            record_id = f"task-ledger-{index}"
            browser_identity = evidence_target.get("contractId") == "browser_identity"
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
                            "description": (
                                "Real Chrome observes the standard favicon link and retrieves its declared SVG asset."
                                if browser_identity
                                else "Real Chrome executes the supported target path."
                            ),
                            "locator": "tests/test_task_ledger_browser.py",
                            "commandId": "verify-product",
                            "expectedResult": (
                                "The standard rel=icon linkage and SVG asset retrieval match browser-identity.json."
                                if browser_identity
                                else "The supported browser interaction passes."
                            ),
                        }
                    ],
                    "negativeEvidence": [
                        {
                            "id": f"{record_id}-negative",
                            "status": "verified",
                            "kind": "end-to-end-test",
                            "description": (
                                "Real Chrome rejects obsolete shortcut-icon linkage, missing declared favicon linkage, or non-SVG primary asset behavior."
                                if browser_identity
                                else "Real Chrome rejects or excludes invalid behavior."
                            ),
                            "locator": "tests/test_task_ledger_browser.py",
                            "commandId": "verify-product",
                            "expectedResult": (
                                "Browser identity drift causes the product proof to fail."
                                if browser_identity
                                else "The invalid browser behavior is absent or rejected."
                            ),
                        }
                    ],
                    "releaseGateIds": ["product-verification"],
                }
            )
            requirements.append(
                self.browser_requirement(index, evidence_target, record_ids=[record_id])
            )
        for operation in self.service_operations():
            operation_id = operation["id"]
            record_id = f"task-ledger-service-{operation_id}"
            service_target = {
                "kind": "contract-item",
                "contractId": "service_interface",
                "itemKind": "operation",
                "itemId": operation_id,
            }
            records.append(
                {
                    "id": record_id,
                    "target": service_target,
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
                self.service_requirement(operation_id, record_ids=[record_id])
            )

        cli_record_id = "task-ledger-cli"
        cli_target = self.cli_requirement(record_ids=[cli_record_id])["targets"][0]
        records.append(
            {
                "id": cli_record_id,
                "target": cli_target,
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
        requirements.append(self.cli_requirement(record_ids=[cli_record_id]))

        self.write_json(
            target / "contracts" / "implementation-evidence.json",
            {
                "$schema": "../schemas/implementation-evidence.schema.json",
                "schemaVersion": 6,
                "mode": "product",
                "commands": [
                    {
                        "id": "verify-product",
                        "command": "./scripts/verify.sh",
                        "purpose": "Run unit, integration, and real-browser proof.",
                        "execution": {
                            "capabilities": ["integration", "end-to-end", "browser"],
                            "harness": {
                                "kind": "repository-file",
                                "locator": "scripts/verify.sh",
                            },
                            "supportsNegativePath": True,
                        },
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
            self.prepare_planning_checkpoint(target)

            self.assertFalse((target / "task_ledger").exists())
            self.assertFalse((target / "tests").exists())
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
            self.assertIn(
                "Task Ledger browser identity proof: standard favicon linkage and asset retrieval passed",
                browser.stdout,
            )
            self.assertIn(
                "viewport and keyboard positive/negative paths passed",
                browser.stdout,
            )

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
