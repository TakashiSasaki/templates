from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
RECORD_ID = re.compile(r"^[a-z][a-z0-9-]*$")


class WebappEvidenceScaffoldTests(unittest.TestCase):
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

    def load_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

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
        self.assertEqual(
            result.returncode,
            0,
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return target

    def scaffold(self, target: Path) -> subprocess.CompletedProcess[str]:
        return self.run_python(target, "scripts/scaffold_webapp_evidence.py")

    def test_scaffold_is_deterministic_non_destructive_and_validator_aligned(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            evidence_path = target / "contracts/implementation-evidence.json"
            original_evidence = evidence_path.read_bytes()

            first = self.scaffold(target)
            second = self.scaffold(target)
            module = self.run_python(
                target, "-m", "scripts.scaffold_webapp_evidence"
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(module.returncode, 0, module.stderr)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(first.stdout, module.stdout)
            self.assertEqual(evidence_path.read_bytes(), original_evidence)

            worklist = json.loads(first.stdout)
            self.assertEqual(worklist["format"], "webapp-implementation-evidence-worklist")
            self.assertEqual(worklist["formatVersion"], 1)
            self.assertEqual(worklist["recordCount"], len(worklist["records"]))
            self.assertEqual(worklist["status"], "missing")
            self.assertGreater(worklist["recordCount"], 0)

            record_ids = [record["id"] for record in worklist["records"]]
            targets = [
                json.dumps(record["target"], sort_keys=True)
                for record in worklist["records"]
            ]
            self.assertEqual(len(record_ids), len(set(record_ids)))
            self.assertEqual(len(targets), len(set(targets)))
            for record in worklist["records"]:
                self.assertRegex(record["id"], RECORD_ID)
                self.assertEqual(record["status"], "missing")
                self.assertEqual(record["implementationBoundary"]["status"], "required")
                self.assertEqual(record["positiveEvidence"][0]["status"], "required")
                self.assertEqual(record["negativeEvidence"][0]["status"], "required")
                self.assertEqual(record["releaseGateIds"], [])

            records = json.loads(json.dumps(worklist["records"]))
            for record in records:
                record["implementationBoundary"].update(
                    {
                        "status": "verified",
                        "locator": "product/implementation",
                    }
                )
                record["releaseGateIds"] = ["product-release"]
                evidence_target = record["target"]
                proof_kind = (
                    "end-to-end-test"
                    if evidence_target.get("kind") == "contract-item"
                    and evidence_target.get("contractId") == "viewports"
                    and evidence_target.get("itemKind")
                    in {"viewport", "input-capability"}
                    else "integration-test"
                )
                for proof in record["positiveEvidence"] + record["negativeEvidence"]:
                    proof.update(
                        {
                            "status": "verified",
                            "kind": proof_kind,
                            "locator": "product/prove.py",
                            "commandId": "product-proof",
                            "expectedResult": "The declared target is covered by the product proof.",
                        }
                    )

            self.write_json(
                evidence_path,
                {
                    "$schema": "../schemas/implementation-evidence.schema.json",
                    "schemaVersion": 1,
                    "mode": "product",
                    "commands": [
                        {
                            "id": "product-proof",
                            "command": "python product/prove.py",
                            "purpose": "Run the product proof.",
                        }
                    ],
                    "releaseGates": [
                        {
                            "id": "product-release",
                            "purpose": "Block release unless the product proof passes.",
                            "commandIds": ["product-proof"],
                        }
                    ],
                    "records": records,
                },
            )

            projected = json.loads(self.scaffold(target).stdout)
            self.assertEqual(projected["status"], "verified")
            self.assertTrue(all(record["status"] == "verified" for record in projected["records"]))

            for script, arguments in (
                ("scripts/validate_contracts.py", ()),
                (
                    ".template-composition/validators/validate_implementation_evidence.py",
                    (".",),
                ),
                ("scripts/validate_webapp_evidence.py", ()),
                ("-m", ("scripts.validate_webapp_evidence",)),
            ):
                result = self.run_python(target, script, *arguments)
                self.assertEqual(
                    result.returncode,
                    0,
                    f"{script}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
                )

    def test_scaffold_and_validator_accept_explicit_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))

            implicit_scaffold = self.scaffold(target)
            explicit_scaffold = self.run_python(
                ROOT,
                str(target / "scripts/scaffold_webapp_evidence.py"),
                str(target),
            )
            self.assertEqual(implicit_scaffold.returncode, 0, implicit_scaffold.stderr)
            self.assertEqual(explicit_scaffold.returncode, 0, explicit_scaffold.stderr)
            self.assertEqual(implicit_scaffold.stdout, explicit_scaffold.stdout)

            explicit_validator = self.run_python(
                ROOT,
                str(target / "scripts/validate_webapp_evidence.py"),
                str(target),
            )
            self.assertEqual(
                explicit_validator.returncode,
                0,
                explicit_validator.stderr,
            )
            self.assertIn("template mode OK", explicit_validator.stdout)

    def test_scaffold_rejects_duplicate_contract_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            surfaces_path = target / "contracts/surfaces.json"
            surfaces = self.load_json(surfaces_path)
            surfaces["surfaces"].append(
                json.loads(json.dumps(surfaces["surfaces"][0]))
            )
            self.write_json(surfaces_path, surfaces)

            result = self.scaffold(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Webapp contracts produce duplicate implementation-evidence targets",
                result.stderr,
            )

    def test_scaffold_rejects_noncanonical_generated_record_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            surfaces_path = target / "contracts/surfaces.json"
            surfaces = self.load_json(surfaces_path)
            surfaces["surfaces"][0]["id"] = "Bad_ID"
            self.write_json(surfaces_path, surfaces)

            result = self.scaffold(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "cannot derive implementation-evidence record id",
                result.stderr,
            )

    def test_validator_reports_malformed_evidence_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_webapp(Path(temp_dir))
            evidence_path = target / "contracts/implementation-evidence.json"
            malformed_cases = (
                "{",
                "[]",
                json.dumps({"mode": "product", "records": "not-a-list"}),
                json.dumps({"mode": "product", "records": [{}]}),
                json.dumps(
                    {"mode": "product", "records": [{"target": "not-an-object"}]}
                ),
            )

            for malformed_content in malformed_cases:
                with self.subTest(malformed_content=malformed_content):
                    evidence_path.write_text(malformed_content, encoding="utf-8")
                    result = self.run_python(
                        target, "scripts/validate_webapp_evidence.py"
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(
                        "ERROR: cannot load Webapp implementation evidence:",
                        result.stderr,
                    )
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
