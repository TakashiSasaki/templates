from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
SCHEMA = ROOT / "components" / "lifecycle.implementation-evidence" / "files" / "schemas" / "implementation-evidence.schema.json"
PROMPT = ROOT / "examples" / "evaluations" / "small-model-clean-room-field-log.txt"
PUBLICATION_CATALOG = ROOT / "docs" / "publication-catalog.json"


class ImplementationEvidencePlanningTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def run_python(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )

    def planning_document(self) -> dict:
        return {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 5,
            "mode": "planning",
            "commands": [],
            "releaseGates": [],
            "records": [],
            "requirements": [
                {
                    "id": "REQ-PLAN-BROWSER-FILTER",
                    "description": "The browser filters caller-visible records by severity.",
                    "targets": [
                        {
                            "kind": "contract-item",
                            "contractId": "routes",
                            "itemKind": "route",
                            "itemId": "home",
                        }
                    ],
                    "recordIds": [],
                    "requiredPositiveProofKinds": ["end-to-end-test"],
                },
                {
                    "id": "REQ-PLAN-CLI-FILTER",
                    "description": "The packaged CLI filters caller-visible records by severity.",
                    "targets": [
                        {
                            "kind": "contract-item",
                            "contractId": "cli_interface",
                            "itemKind": "entrypoint",
                            "itemId": "records",
                        }
                    ],
                    "recordIds": [],
                    "requiredPositiveProofKinds": ["integration-test"],
                },
            ],
        }

    def materialize(
        self, root: Path, *, include: list[str] | None = None
    ) -> Path:
        target = root / "consumer"
        config = root / "composition.json"
        self.write_json(
            config,
            {
                "schema_version": 1,
                "recipe": "webapp",
                "components": {"include": include or [], "exclude": []},
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

    def test_schema_and_validators_accept_truthful_planning_but_release_readiness_rejects_it(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        planning = self.planning_document()
        validator.validate(planning)

        missing_targets = json.loads(json.dumps(planning))
        del missing_targets["requirements"][0]["targets"]
        self.assertTrue(list(validator.iter_errors(missing_targets)))

        empty_targets = json.loads(json.dumps(planning))
        empty_targets["requirements"][0]["targets"] = []
        self.assertTrue(list(validator.iter_errors(empty_targets)))

        premature = json.loads(json.dumps(planning))
        premature["requirements"][0]["recordIds"] = ["premature-record"]
        self.assertTrue(list(validator.iter_errors(premature)))

        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir), include=["capability.cli"])
            evidence_path = target / "contracts" / "implementation-evidence.json"
            self.write_json(evidence_path, planning)

            generic = self.run_python(
                target,
                ".template-composition/validators/validate_implementation_evidence.py",
                ".",
            )
            self.assertEqual(generic.returncode, 0, generic.stdout + generic.stderr)
            self.assertIn("target-bound", generic.stdout)
            self.assertIn("Release readiness: NOT READY", generic.stdout)

            webapp = self.run_python(target, "scripts/validate_webapp_evidence.py")
            self.assertEqual(webapp.returncode, 0, webapp.stdout + webapp.stderr)
            self.assertIn("Webapp planning targets and browser proof strength: OK", webapp.stdout)

            scaffold = self.run_python(target, "scripts/scaffold_webapp_evidence.py")
            self.assertEqual(scaffold.returncode, 0, scaffold.stdout + scaffold.stderr)
            worklist = json.loads(scaffold.stdout)
            self.assertEqual(worklist["formatVersion"], 3)
            self.assertEqual(worklist["requirementLedgerStatus"], "verified")
            self.assertEqual(worklist["status"], "missing")
            self.assertEqual(
                [item["id"] for item in worklist["requirements"]],
                ["REQ-PLAN-BROWSER-FILTER", "REQ-PLAN-CLI-FILTER"],
            )
            self.assertTrue(
                all(item["status"] == "missing" for item in worklist["requirements"])
            )
            self.assertTrue(
                all(item["recordIds"] == [] for item in worklist["requirements"])
            )

            readiness = self.run_python(
                target,
                ".template-composition/validators/validate_implementation_evidence.py",
                ".",
                "--release-readiness",
            )
            self.assertNotEqual(readiness.returncode, 0)
            self.assertIn("mode 'planning' is not 'product'", readiness.stderr)

            unknown = self.planning_document()
            unknown["requirements"][0]["targets"][0]["contractId"] = "not_registered"
            self.write_json(evidence_path, unknown)
            rejected = self.run_python(
                target,
                ".template-composition/validators/validate_implementation_evidence.py",
                ".",
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("unknown contract target not_registered", rejected.stderr)

    def test_planning_keeps_release_execution_in_template_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(
                Path(temp_dir), include=["lifecycle.release-bundle"]
            )
            self.write_json(
                target / "contracts" / "implementation-evidence.json",
                self.planning_document(),
            )
            execution = json.loads(
                (target / "contracts" / "release-execution.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(execution["mode"], "template")
            self.assertEqual(execution["commands"], [])

            validation = self.run_python(
                target,
                ".template-composition/validators/validate_release_execution.py",
                ".",
            )
            self.assertEqual(
                validation.returncode, 0, validation.stdout + validation.stderr
            )
            self.assertIn("Release execution validation: OK", validation.stdout)

    def test_template_is_not_release_ready_and_prompt_uses_target_bound_planning_before_coding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
            readiness = self.run_python(
                target,
                ".template-composition/validators/validate_implementation_evidence.py",
                ".",
                "--release-readiness",
            )
            self.assertNotEqual(readiness.returncode, 0)
            self.assertIn("mode 'template' is not 'product'", readiness.stderr)

        prompt = PROMPT.read_text(encoding="utf-8")
        self.assertIn("Before product coding", prompt)
        self.assertIn("implementation-evidence planning state", prompt)
        self.assertIn("contract target", prompt)
        self.assertIn("empty recordIds", prompt)
        self.assertIn("requiredPositiveProofKinds", prompt)
        self.assertIn("Preserve those IDs", prompt)

    def test_v5_migration_guide_is_published(self) -> None:
        catalog = json.loads(PUBLICATION_CATALOG.read_text(encoding="utf-8"))
        documents = {document["id"]: document for document in catalog["documents"]}
        self.assertEqual(
            documents["implementation-evidence-v5-migration"]["source"],
            "components/lifecycle.implementation-evidence/files/docs/migrations/implementation-evidence-v4-to-v5.md",
        )
        self.assertFalse(documents["implementation-evidence-v5-migration"]["optional"])
        self.assertFalse(documents["implementation-evidence-v5-migration"]["home"])


if __name__ == "__main__":
    unittest.main()
