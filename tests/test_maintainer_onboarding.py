import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MaintainerOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.guide = (ROOT / "docs/maintainer-onboarding.md").read_text(encoding="utf-8")
        self.automation = (ROOT / "docs/publication-automation.md").read_text(encoding="utf-8")
        self.guide_flat = " ".join(self.guide.split())
        self.automation_flat = " ".join(self.automation.split())

    def test_site_entrypoint_preserves_consumer_route_and_adds_maintainer_route(self):
        self.assertIn("Five independent authorities", self.readme)
        self.assertIn("**Modeling**", self.readme)
        self.assertIn("Maintain this repository", self.readme)
        self.assertIn("maintainer-onboarding.md", self.readme)
        self.assertIn("A first-time application author normally starts", self.readme)
        self.assertIn("A new Integration release alone is not Site-adoption authorization", self.readme)

    def test_guide_maps_all_authorities_sources_checks_and_boundaries(self):
        for authority in ("Modeling", "Composition", "Policy", "Integration", "Site"):
            with self.subTest(authority=authority):
                self.assertIn(f"| {authority} |", self.guide)
        for required in (
            "branch name",
            "full SHA",
            "separate checkout",
            "records/",
            "generated/",
            ".agent-policy.yml",
            "publication-sources.json",
            "integration-source.json",
            "Policy Work-ledger",
            "Stack PRs only within one authority",
            "current capability",
            "selected input",
            "actually deployed",
            "unknown",
            "does not mean deployed",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.guide_flat)

    def test_publication_runbook_and_guide_cover_current_event_chain(self):
        for workflow in (
            "modeling-ci.yml",
            "reference-consumer-publication.yml",
            "integration-compatibility.yml",
            "provider-publication-dispatch.yml",
            "integration-reconcile.yml",
            "integration-promotion-notify.yml",
            "publication-reconcile.yml",
            "site-publication-notify.yml",
            "deploy-pages.yml",
        ):
            with self.subTest(workflow=workflow):
                self.assertIn(workflow, self.guide)
        for event in (
            "publication.provider-qualified",
            "publication.integration-promoted",
            "automation/publication-*",
            "automation/site-publication-*",
            "automatic=true",
            "automatic=false",
        ):
            with self.subTest(event=event):
                self.assertIn(event, self.guide_flat)
        for distinction in (
            "notification carries a candidate fact",
            "auto-merge",
            "required review",
            "actual merge",
            "deployment",
            "kill switch",
            "mode change does not replay",
        ):
            with self.subTest(distinction=distinction):
                self.assertIn(distinction, self.guide_flat)
                self.assertIn(distinction, self.automation_flat)

    def test_branch_local_and_generated_routes_are_present(self):
        for path in (
            "docs/maintainer-onboarding.md",
            "docs/publication-automation.md",
            "MAINTENANCE.md",
            "PUBLISHING.md",
            "policy/project.md",
            ".agents/skills/site-publication-cutover/SKILL.md",
        ):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())
        for path in ("README.md", "MAINTENANCE.md", "PUBLISHING.md", "policy/project.md"):
            with self.subTest(path=path):
                self.assertIn("docs/publication-automation.md", (ROOT / path).read_text(encoding="utf-8"))
        for required in ("docs/maintainer-onboarding.md", "docs/publication-automation.md"):
            with self.subTest(required=required):
                self.assertIn(required, (ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        catalog = json.loads((ROOT / "docs/publication-catalog.json").read_text(encoding="utf-8"))
        catalog_sources = {entry["source"] for entry in catalog["documents"]}
        self.assertIn("docs/maintainer-onboarding.md", catalog_sources)
        self.assertIn("docs/publication-automation.md", catalog_sources)

    def test_machine_projection_labels_current_and_historical_contracts(self):
        agent = json.loads((ROOT / "agent.json").read_text(encoding="utf-8"))
        integration = agent["authorities"]["integration"]
        self.assertEqual(integration["contract"], "Integrated Publication Bundle v4")
        self.assertIn("Integrated Publication Bundle v3", integration["historical_compatibility"])
        self.assertEqual(agent["publication_state"]["selected_input"], "integration-source.json")
        self.assertIn("Pages artifact", agent["publication_state"]["deployed_evidence"])


if __name__ == "__main__":
    unittest.main()
