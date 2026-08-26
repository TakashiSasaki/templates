from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
BROWSER_SENSITIVE_ITEM_KINDS = {"input-capability", "viewport"}


class WebappEvidenceProofStrengthTests(unittest.TestCase):
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
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def materialize_webapp(self, root: Path) -> Path:
        target = root / "consumer"
        config = root / "composition.json"
        self.write_json(
            config,
            {
                "schema_version": 1,
                "recipe": "webapp",
                "components": {"include": [], "exclude": []},
                "parameters": {},
            },
        )
        result = self.run_python(
            ROOT,
            str(COMPOSER),
            "apply",
            "--config",
            str(config),
            "--target",
            str(target),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return target

    def worklist_records(self, target: Path) -> list[dict]:
        result = self.run_python(target, "scripts/scaffold_webapp_evidence.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["records"]

    def complete_records(
        self,
        records: list[dict],
        proof_kind: str,
        execution_class: str,
    ) -> list[dict]:
        completed = json.loads(json.dumps(records))
        for index, record in enumerate(completed):
            record_id = record["id"]
            record["positiveEvidence"] = [
                {
                    "id": f"{record_id}-positive-proof",
                    "status": "verified",
                    "kind": proof_kind,
                    "executionClass": execution_class,
                }
            ]
            record["negativeEvidence"] = [
                {
                    "id": f"{record_id}-negative-proof",
                    "status": "verified",
                    "kind": proof_kind,
                    "executionClass": execution_class,
                }
            ]
            record["releaseGateIds"] = ["product-release"]
            self.assertEqual(record["target"]["kind"], "contract-item", index)
        return completed

    def validate(
        self, target: Path, records: list[dict]
    ) -> subprocess.CompletedProcess[str]:
        self.write_json(
            target / "contracts" / "implementation-evidence.json",
            {"mode": "product", "records": records},
        )
        return self.run_python(target, "scripts/validate_webapp_evidence.py")

    def browser_sensitive(self, record: dict) -> bool:
        target = record["target"]
        if (
            target["contractId"] == "viewports"
            and target["itemKind"] in BROWSER_SENSITIVE_ITEM_KINDS
        ):
            return True
        return target["contractId"] == "routes" and target["itemKind"] == "route"

    def test_end_to_end_label_with_static_execution_is_not_browser_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            records = self.complete_records(
                self.worklist_records(target),
                "end-to-end-test",
                "static-inspection",
            )

            result = self.validate(target, records)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("browser-sensitive Webapp target", result.stderr)
            self.assertIn("executionClass='browser-interaction'", result.stderr)
            self.assertIn("static inspection", result.stderr)
            self.assertIn("'viewport'", result.stderr)
            self.assertIn("'input-capability'", result.stderr)
            self.assertIn("'routes'", result.stderr)

    def test_http_level_integration_proof_is_insufficient_for_browser_sensitive_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            records = self.complete_records(
                self.worklist_records(target),
                "integration-test",
                "process-integration",
            )

            result = self.validate(target, records)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("browser-sensitive Webapp target", result.stderr)
            self.assertIn("process integration is not browser interaction", result.stderr)

    def test_browser_interaction_proofs_satisfy_only_the_targets_that_need_them(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            records = self.complete_records(
                self.worklist_records(target),
                "integration-test",
                "process-integration",
            )
            strengthened = 0
            for record in records:
                if not self.browser_sensitive(record):
                    continue
                record["positiveEvidence"][0]["kind"] = "end-to-end-test"
                record["positiveEvidence"][0]["executionClass"] = "browser-interaction"
                record["negativeEvidence"][0]["kind"] = "accessibility-test"
                record["negativeEvidence"][0]["executionClass"] = "browser-interaction"
                strengthened += 1

            self.assertGreater(strengthened, 0)
            self.assertTrue(
                any(
                    not self.browser_sensitive(record)
                    and record["positiveEvidence"][0]["executionClass"]
                    == "process-integration"
                    for record in records
                )
            )

            result = self.validate(target, records)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("coverage and proof strength: OK", result.stdout)

    def test_deferred_browser_interaction_is_structurally_declared(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            records = self.complete_records(
                self.worklist_records(target),
                "integration-test",
                "process-integration",
            )
            for record in records:
                if not self.browser_sensitive(record):
                    continue
                for proof in (
                    record["positiveEvidence"][0],
                    record["negativeEvidence"][0],
                ):
                    proof["kind"] = "end-to-end-test"
                    proof["executionClass"] = "browser-interaction"
                    proof["status"] = "deferred"
                    proof["deferredReason"] = "Browser runtime unavailable."

            result = self.validate(target, records)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
