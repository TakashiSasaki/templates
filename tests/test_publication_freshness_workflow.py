from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
FRESHNESS_WORKFLOW = ROOT / ".github/workflows/check-publication-freshness.yml"
FRESHNESS_CONTRACT = ROOT / "PUBLICATION_FRESHNESS.md"


class PublicationFreshnessWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow_text = FRESHNESS_WORKFLOW.read_text(encoding="utf-8")
        self.workflow = yaml.load(self.workflow_text, Loader=yaml.BaseLoader)
        self.assertIsInstance(self.workflow, dict)

    def test_workflow_is_read_only_and_runs_on_relevant_site_changes(self) -> None:
        triggers = self.workflow["on"]
        pull_request = triggers["pull_request"]

        self.assertEqual(["site"], pull_request["branches"])
        self.assertIn("publication-sources.json", pull_request["paths"])
        self.assertIn("site-manifest.json", pull_request["paths"])
        self.assertIn("scripts/**", pull_request["paths"])
        self.assertIn("PUBLICATION_FRESHNESS.md", pull_request["paths"])
        self.assertEqual("23 17 * * *", triggers["schedule"][0]["cron"])
        self.assertIn("workflow_dispatch", triggers)

        self.assertEqual({"contents": "read"}, self.workflow["permissions"])
        self.assertNotIn("pages: write", self.workflow_text)
        self.assertNotIn("id-token: write", self.workflow_text)
        self.assertNotIn("actions/configure-pages@", self.workflow_text)
        self.assertNotIn("actions/deploy-pages@", self.workflow_text)

    def test_current_composition_head_is_resolved_to_an_exact_sha_snapshot(self) -> None:
        resolve = self.workflow["jobs"]["resolve"]
        steps = {step["name"]: step for step in resolve["steps"]}

        head_step = steps["Resolve current Composition HEAD"]
        self.assertEqual("actions/github-script@v8", head_step["uses"])
        script = head_step["with"]["script"]
        self.assertIn("github.rest.repos.getBranch", script)
        self.assertIn("branch: 'composition'", script)
        self.assertIn("return data.commit.sha;", script)

        classify_step = steps["Classify publication freshness"]
        self.assertIn(
            "site-source/scripts/classify_publication_freshness.py",
            classify_step["run"],
        )
        self.assertEqual(
            "${{ steps.composition_head.outputs.result }}",
            classify_step["env"]["CURRENT_COMPOSITION"],
        )

    def test_candidate_uses_normal_full_build_with_composition_only_override(self) -> None:
        candidate = self.workflow["jobs"]["candidate_build"]

        self.assertEqual(
            "github.repository == 'TakashiSasaki/templates'",
            candidate["if"],
        )
        self.assertEqual("./.github/workflows/build-pages.yml", candidate["uses"])
        self.assertEqual(
            "${{ needs.resolve.outputs.site_revision }}",
            candidate["with"]["site_ref"],
        )
        self.assertEqual(
            "${{ needs.resolve.outputs.composition_head }}",
            candidate["with"]["composition_ref"],
        )
        self.assertNotIn("policy_ref", candidate["with"])
        self.assertEqual({"contents": "read"}, candidate["permissions"])

    def test_report_distinguishes_unexecuted_failure_and_divergence(self) -> None:
        report = self.workflow["jobs"]["report"]
        self.assertIn("github.repository == 'TakashiSasaki/templates'", report["if"])
        steps = {step["name"]: step for step in report["steps"]}
        run = steps["Report publication freshness"]["run"]

        skipped_position = run.index('if [ "$CANDIDATE_RESULT" = "skipped" ]; then')
        failure_position = run.index('if [ "$CANDIDATE_RESULT" != "success" ]; then')
        warning_position = run.index('if [ "$RELATION" = "different" ]; then')
        self.assertLess(skipped_position, failure_position)
        self.assertLess(failure_position, warning_position)
        self.assertIn("no compatibility conclusion is available", run)
        self.assertIn("does not pass the normal full Site publication build", run)
        self.assertIn("advancing the reviewed lock remains an explicit Site review decision", run)
        self.assertIn("Policy source: reviewed Site lock", run)

    def test_normative_contract_documents_diagnostic_scope(self) -> None:
        contract = FRESHNESS_CONTRACT.read_text(encoding="utf-8")

        self.assertIn("check-publication-freshness.yml", contract)
        self.assertIn("reviewed immutable release input", contract)
        self.assertIn("Policy remains at the reviewed Site lock", contract)
        self.assertIn("warning", contract)
        self.assertIn("does not update the lock automatically", contract)
        self.assertIn("FRESHNESS.md", contract)
        self.assertIn("Site maintainer", contract)


if __name__ == "__main__":
    unittest.main()
