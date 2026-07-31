from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/contract-validation.yml"


class WorkflowConfigurationTests(unittest.TestCase):
    def test_contract_validation_is_not_restricted_to_template_source_branches(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("on:\n  push:\n  pull_request:\n", workflow)
        self.assertNotIn("branches:", workflow)
        self.assertNotIn("branches-ignore:", workflow)


if __name__ == "__main__":
    unittest.main()
