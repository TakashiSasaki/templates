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

        self.assertEqual(
            ["site", "codex/site-composition-playground-v1-shell"],
            pull_request["branches"],
        )
        expected_paths = {
            ".github/workflows/check-publication-freshness.yml",
            ".github/workflows/build-pages.yml",
            "PUBLICATION_FRESHNESS.md",
            "publication-sources.json",
            "site-manifest.json",
            "scripts/**",
            "tests/**",
            "requirements.txt",
            "zensical.template.toml",
        }
        self.assertEqual(expected_paths, set(pull_request["paths"]))
        self.assertEqual("23 17 * * *", triggers["schedule"][0]["cron"])
        self.assertIn("workflow_dispatch", triggers)

        self.assertEqual({"contents": "read"}, self.workflow["permissions"])
        self.assertNotIn("pages: write", self.workflow_text)
        self.assertNotIn("id-token: write", self.workflow_text)
        self.assertNotIn("actions/configure-pages@", self.workflow_text)
        self.assertNotIn("actions/deploy-pages@", self.workflow_text)

    def test_concurrency_only_cancels_superseded_pull_request_runs(self) -> None:
        concurrency = self.workflow["concurrency"]
        self.assertEqual("publication-freshness-${{ github.ref }}", concurrency["group"])
        self.assertEqual(
            "${{ github.event_name == 'pull_request' }}",
            concurrency["cancel-in-progress"],
        )

    def test_candidate_scope_uses_exact_pr_diff_and_fails_closed(self) -> None:
        resolve = self.workflow["jobs"]["resolve"]
        outputs = resolve["outputs"]
        self.assertEqual(
            "${{ steps.candidate_scope.outputs.required }}",
            outputs["candidate_required"],
        )
        self.assertEqual(
            "${{ steps.candidate_scope.outputs.reason }}",
            outputs["candidate_reason"],
        )

        steps = {step["name"]: step for step in resolve["steps"]}
        checkout = steps["Check out Site diagnostic implementation"]
        self.assertEqual("0", checkout["with"]["fetch-depth"])
        self.assertEqual("false", checkout["with"]["persist-credentials"])

        scope = steps["Select candidate build scope"]
        self.assertEqual("${{ github.event_name }}", scope["env"]["EVENT_NAME"])
        self.assertEqual(
            "${{ github.event.pull_request.base.sha }}",
            scope["env"]["BASE_SHA"],
        )
        self.assertEqual(
            "${{ github.event.pull_request.head.sha }}",
            scope["env"]["HEAD_SHA"],
        )
        run = scope["run"]
        self.assertIn('if [ "$EVENT_NAME" != pull_request ]; then', run)
        self.assertIn("required=true", run)
        self.assertIn("scheduled or manual diagnostic", run)
        self.assertIn(
            'git -C site-source diff --name-only --no-renames "$BASE_SHA" "$HEAD_SHA"',
            run,
        )
        self.assertIn('test -s "$RUNNER_TEMP/publication-freshness-paths.txt"', run)
        self.assertIn(
            "python -I site-source/scripts/classify_site_browser_acceptance.py",
            run,
        )
        self.assertIn('--output "$GITHUB_OUTPUT"', run)

        selection_report = steps["Report candidate build selection"]
        selection_run = selection_report["run"]
        self.assertIn('case "$CANDIDATE_REQUIRED" in', selection_run)
        self.assertIn("Unexpected candidate build selection", selection_run)

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

    def test_candidate_uses_normal_full_build_only_when_scope_requires_it(self) -> None:
        candidate = self.workflow["jobs"]["candidate_build"]

        condition = candidate["if"]
        self.assertIn("github.repository == 'TakashiSasaki/templates'", condition)
        self.assertIn(
            "needs.resolve.outputs.candidate_required == 'true'",
            condition,
        )
        self.assertEqual(["resolve"], [candidate["needs"]])
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

    def test_report_accepts_only_required_success_or_nonapplicable_skip(self) -> None:
        report = self.workflow["jobs"]["report"]
        self.assertIn("github.repository == 'TakashiSasaki/templates'", report["if"])
        steps = {step["name"]: step for step in report["steps"]}
        report_step = steps["Report publication freshness"]
        run = report_step["run"]

        self.assertEqual(
            "${{ needs.resolve.outputs.site_revision }}",
            report_step["env"]["SITE_REVISION"],
        )
        self.assertEqual(
            "${{ needs.resolve.outputs.candidate_required }}",
            report_step["env"]["CANDIDATE_REQUIRED"],
        )
        self.assertEqual(
            "${{ needs.resolve.outputs.candidate_reason }}",
            report_step["env"]["CANDIDATE_REASON"],
        )
        self.assertIn("Site revision:", run)
        self.assertIn('case "$CANDIDATE_REQUIRED:$CANDIDATE_RESULT" in', run)
        self.assertIn("true:success", run)
        self.assertIn("false:skipped", run)
        self.assertIn("true:skipped", run)
        self.assertIn("false:success", run)
        self.assertIn("non-applicable for this CI-observability-only pull request", run)
        self.assertIn("no compatibility conclusion is available", run)
        self.assertIn("unexpectedly executed", run)
        self.assertIn("does not pass the required normal full Site publication build", run)
        self.assertIn('case "$RELATION" in', run)
        self.assertIn("advancing the reviewed lock remains an explicit Site review decision", run)
        self.assertIn(
            "compatibility is intentionally not re-evaluated for this CI-observability-only pull request",
            run,
        )
        self.assertIn("Unexpected publication freshness relation", run)
        self.assertIn("Policy source: reviewed Site lock", run)

    def test_normative_contract_documents_targeted_diagnostic_scope(self) -> None:
        contract = FRESHNESS_CONTRACT.read_text(encoding="utf-8")

        self.assertIn("check-publication-freshness.yml", contract)
        self.assertIn("reviewed immutable release input", contract)
        self.assertIn("Policy remains at the reviewed Site lock", contract)
        self.assertIn("does not update the lock automatically", contract)
        self.assertIn("FRESHNESS.md", contract)
        self.assertIn("Site maintainer", contract)
        self.assertIn("two full publication builds", contract)
        self.assertIn("CI-observability-only", contract)
        self.assertIn("fail-closed", contract)
        self.assertIn("Scheduled and `workflow_dispatch` diagnostics", contract)
        self.assertIn("always execute the full candidate build", contract)
        self.assertIn(
            "workflow records that no new compatibility conclusion was produced",
            contract,
        )


if __name__ == "__main__":
    unittest.main()
