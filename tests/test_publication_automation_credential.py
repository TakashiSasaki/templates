from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CREDENTIAL = "${{ secrets.PUBLICATION_AUTOMATION_TOKEN }}"
WORKFLOWS = (
    "publication-reconcile.yml",
    "site-publication-notify.yml",
)


def workflow_gh_tokens(workflow):
    environments = [workflow.get("env") or {}]
    for job in (workflow.get("jobs") or {}).values():
        environments.append(job.get("env") or {})
        for step in job.get("steps") or []:
            environments.append(step.get("env") or {})
    return [environment["GH_TOKEN"] for environment in environments if "GH_TOKEN" in environment]


class PublicationAutomationCredentialTests(unittest.TestCase):
    def test_state_changing_workflows_use_the_dedicated_credential(self):
        for name in WORKFLOWS:
            with self.subTest(workflow=name):
                workflow = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
                secret_tokens = [value for value in workflow_gh_tokens(workflow) if "secrets." in value]
                self.assertEqual(secret_tokens, [EXPECTED_CREDENTIAL])


if __name__ == "__main__":
    unittest.main()
