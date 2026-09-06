"""Keep reference acceptance execution bound to declared evidence commands."""
import json
import shlex
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


class ReferenceEvidenceCommandTests(unittest.TestCase):
    def test_browser_job_executes_declared_commands(self):
        evidence = json.loads((ROOT / "contracts/implementation-evidence.json").read_text())
        workflow = yaml.safe_load((ROOT / ".github/workflows/reference-consumer.yml").read_text())
        job = workflow["jobs"]["browser"]
        self.assertNotIn("if", job)
        for command in evidence["commands"]:
            with self.subTest(command=command["id"]):
                tokens = shlex.split(command["command"])
                matches = [step for step in job["steps"] if "run" in step and shlex.split(step["run"]) == tokens]
                self.assertEqual(len(matches), 1, command["command"])
                self.assertNotIn("if", matches[0])
                self.assertNotIn("continue-on-error", matches[0])
                self.assertNotIn("working-directory", matches[0])
                harness = command["execution"]["harness"]
                self.assertEqual(harness["kind"], "repository-file")
                self.assertIn(harness["locator"], tokens)
                self.assertTrue((ROOT / harness["locator"]).is_file())


if __name__ == "__main__":
    unittest.main()
