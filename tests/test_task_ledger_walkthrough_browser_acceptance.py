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
        viewports_path = target / "contracts" / "viewports.json"
        viewports = json.loads(viewports_path.read_text(encoding="utf-8"))
        base = next(item for item in viewports["viewports"] if item["id"] == "base")
        base["minWidthPx"] = 390
        self.write_json(viewports_path, viewports)

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
        for index, evidence_target in enumerate(self.expected_targets(target), 1):
            record_id = f"task-ledger-{index}"
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
        self.write_json(
            target / "contracts" / "implementation-evidence.json",
            {
                "$schema": "../schemas/implementation-evidence.schema.json",
                "schemaVersion": 1,
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
                "records": records,
            },
        )

    def test_walkthrough_reaches_real_browser_product_mode_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
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
