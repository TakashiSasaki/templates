from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/schema-validation.yml"


class SystemChromeDriverWorkflowTests(unittest.TestCase):
    def test_schema_workflow_uses_only_runner_chromedriver_for_real_browser_job(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("- name: Select runner-provided ChromeDriver"), 1)
        self.assertNotIn("scripts/prepare_chromedriver.py", workflow)
        self.assertEqual(workflow.count("command -v chromedriver"), 1)
        self.assertEqual(
            workflow.count('echo "CHROMEWEBDRIVER=$driver_path" >> "$GITHUB_ENV"'),
            1,
        )
        self.assertEqual(workflow.count('"$CHROMEWEBDRIVER" --version'), 1)
        browser_job = workflow.split("\n  real_browser:\n", 1)[1].split(
            "\n  validate:\n", 1
        )[0]
        core_jobs = workflow.split("\n  real_browser:\n", 1)[0]
        self.assertIn("Select runner-provided ChromeDriver", browser_job)
        self.assertNotIn("Select runner-provided ChromeDriver", core_jobs)
        self.assertNotIn("\n          chromedriver --version\n", workflow)


if __name__ == "__main__":
    unittest.main()
