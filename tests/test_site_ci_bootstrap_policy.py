from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SiteCIBootstrapPolicyTests(unittest.TestCase):
    def test_active_workflows_use_runner_tools_without_runtime_selection(self) -> None:
        workflows = sorted((ROOT / ".github/workflows").glob("*.yml"))
        self.assertTrue(workflows)
        for path in workflows:
            text = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertNotIn("actions/setup-python", text)
                self.assertNotIn("python-version", text)
                self.assertNotIn("actions/setup-node", text)
                self.assertNotIn("node-version", text)
                self.assertNotRegex(text, r"\bbunx?\b")
                self.assertNotIn("windows-", text.lower())
                for runner in re.findall(r"^\s*runs-on:\s*(.+)$", text, re.MULTILINE):
                    self.assertIn("ubuntu", runner.lower())

    def test_runner_native_commands_are_explicit(self) -> None:
        for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertNotRegex(text, r"(?m)^\s*run:\s+python\s")


if __name__ == "__main__":
    unittest.main()
