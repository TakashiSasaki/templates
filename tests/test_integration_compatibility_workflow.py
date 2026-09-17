"""Exact candidate compatibility must stop at the reviewed Integration Bundle."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "9430a7dc124bbcfe66847c04e584bd54bed29ad3"

class IntegrationCompatibilityTests(unittest.TestCase):
    def test_reusable_contract_and_producer_are_the_same_immutable_revision(self):
        text = (ROOT / ".github/workflows/integration-compatibility.yml").read_text()
        self.assertIn("integration-qualification.yml@" + PIN, text)
        self.assertIn("producer_ref: " + PIN, text)
        self.assertIn("policy_ref: ${{ github.event.pull_request.head.sha || github.sha }}", text)
        self.assertNotIn("composition_ref:", text)
        pull_request = text.split("  pull_request:", 1)[1].split("  push:", 1)[0]
        self.assertNotIn("branches:", pull_request)
        self.assertIn("ready_for_review", text)
        self.assertIn("!github.event.pull_request.draft", text)
        self.assertIn("branches: [policy]", text)
        self.assertIn("actions: read", text)
        self.assertNotRegex(text, r"(?m)^\s*(?:pages|id-token): write")
        self.assertEqual(text.count("      contents: write"), 1)
        notify = text.split("  notify-integration:", 1)[1]
        self.assertIn("github.event_name == 'push'", notify)
        self.assertIn("github.ref == 'refs/heads/policy'", notify)
        self.assertIn("publication.provider-qualified", notify)
        self.assertIn("client_payload[provider_revision]", notify)
        self.assertNotIn("client_payload[producer_ref]", notify)
        self.assertNotIn("build-pages", text)
        self.assertNotIn("site_ref:", text)

    def test_provider_workflows_do_not_execute_site(self):
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            text = path.read_text()
            self.assertNotIn("build-pages.yml@", text, str(path))
            self.assertNotIn(".site-publication-protocol", text, str(path))
            self.assertNotIn("deploy-pages@", text, str(path))
            self.assertNotIn("upload-pages-artifact@", text, str(path))
