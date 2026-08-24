from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


class WebappEvidenceTargetFailClosedTests(unittest.TestCase):
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
        payload = json.loads(result.stdout)
        return payload["records"]

    def validate(self, target: Path, records: list[dict]) -> subprocess.CompletedProcess[str]:
        self.write_json(
            target / "contracts" / "implementation-evidence.json",
            {"mode": "product", "records": records},
        )
        return self.run_python(target, "scripts/validate_webapp_evidence.py")

    def test_validator_fails_closed_on_missing_unknown_and_duplicate_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            records = self.worklist_records(target)
            self.assertGreater(len(records), 1)

            missing = self.validate(target, records[1:])
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn(
                "missing Webapp implementation-evidence target:",
                missing.stderr,
            )

            unknown_record = json.loads(json.dumps(records[0]))
            unknown_record["id"] = "unknown-target"
            unknown_record["target"]["itemId"] = "unknown-item"
            unknown = self.validate(target, [*records, unknown_record])
            self.assertNotEqual(unknown.returncode, 0)
            self.assertIn(
                "unknown Webapp implementation-evidence target:",
                unknown.stderr,
            )

            duplicate_record = json.loads(json.dumps(records[0]))
            duplicate_record["id"] = "duplicate-target"
            duplicate = self.validate(target, [*records, duplicate_record])
            self.assertNotEqual(duplicate.returncode, 0)
            expected_key = (
                "contract-item",
                records[0]["target"]["contractId"],
                records[0]["target"]["itemKind"],
                records[0]["target"]["itemId"],
            )
            self.assertIn(
                f"duplicate Webapp implementation-evidence target: {expected_key}",
                duplicate.stderr,
            )


if __name__ == "__main__":
    unittest.main()
