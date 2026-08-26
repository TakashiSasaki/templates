from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
BROWSER_SENSITIVE_ITEM_KINDS = {"input-capability", "route", "viewport"}


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

    def complete_records(self, records: list[dict], proof_kind: str) -> list[dict]:
        completed = json.loads(json.dumps(records))
        for index, record in enumerate(completed):
            record_id = record["id"]
            record["positiveEvidence"] = [
                {
                    "id": f"{record_id}-positive-proof",
                    "kind": proof_kind,
                }
            ]
            record["negativeEvidence"] = [
                {
                    "id": f"{record_id}-negative-proof",
                    "kind": proof_kind,
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

    def test_http_level_integration_proof_is_insufficient_for_browser_sensitive_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            records = self.complete_records(
                self.worklist_records(target), "integration-test"
            )

            result = self.validate(target, records)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("browser-sensitive Webapp target", result.stderr)
            self.assertIn("end-to-end-test", result.stderr)
            self.assertIn("accessibility-test", result.stderr)
            self.assertIn("'viewport'", result.stderr)
            self.assertIn("'input-capability'", result.stderr)
            self.assertIn("positive browser-level proof", result.stderr)
            self.assertIn("negative browser-level proof", result.stderr)

    def test_browser_level_proofs_satisfy_only_the_targets_that_need_them(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            records = self.complete_records(
                self.worklist_records(target), "integration-test"
            )
            strengthened = 0
            for record in records:
                target_record = record["target"]
                if target_record["itemKind"] not in BROWSER_SENSITIVE_ITEM_KINDS:
                    continue
                record["positiveEvidence"][0]["kind"] = "end-to-end-test"
                record["negativeEvidence"][0]["kind"] = "accessibility-test"
                strengthened += 1

            self.assertGreater(strengthened, 0)
            self.assertTrue(
                any(
                    record["target"]["itemKind"] not in BROWSER_SENSITIVE_ITEM_KINDS
                    and record["positiveEvidence"][0]["kind"] == "integration-test"
                    for record in records
                )
            )

            result = self.validate(target, records)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("coverage and proof strength: OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
