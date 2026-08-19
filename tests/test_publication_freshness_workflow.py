from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRESHNESS_WORKFLOW = ROOT / ".github/workflows/check-publication-freshness.yml"


class PublicationFreshnessWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = FRESHNESS_WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_is_read_only_and_runs_on_relevant_site_changes(self) -> None:
        trigger_block = self.workflow.split("\npermissions:\n", maxsplit=1)[0]

        self.assertIn(
            "  pull_request:\n    branches:\n      - site",
            trigger_block,
        )
        self.assertIn("  schedule:", trigger_block)
        self.assertIn("cron: '23 17 * * *'", trigger_block)
        self.assertIn("  workflow_dispatch:", trigger_block)
        self.assertIn("'publication-sources.json'", trigger_block)
        self.assertIn("'site-manifest.json'", trigger_block)
        self.assertIn("'scripts/**'", trigger_block)

        self.assertIn("permissions:\n  contents: read", self.workflow)
        self.assertNotIn("pages: write", self.workflow)
        self.assertNotIn("id-token: write", self.workflow)
        self.assertNotIn("actions/configure-pages@", self.workflow)
        self.assertNotIn("actions/deploy-pages@", self.workflow)

    def test_current_composition_head_is_resolved_to_an_exact_sha_snapshot(self) -> None:
        self.assertIn("actions/github-script@v8", self.workflow)
        self.assertIn("github.rest.repos.getBranch", self.workflow)
        self.assertIn("branch: 'composition'", self.workflow)
        self.assertIn("return data.commit.sha;", self.workflow)
        self.assertIn(
            'full_sha = re.compile(r"\\A[0-9a-f]{40}\\Z")',
            self.workflow,
        )
        self.assertIn(
            'relation = "current" if locked == current else "different"',
            self.workflow,
        )

    def test_candidate_uses_the_normal_complete_site_build_with_exact_overrides(self) -> None:
        self.assertIn("uses: ./.github/workflows/build-pages.yml", self.workflow)
        self.assertIn(
            "site_ref: ${{ needs.resolve.outputs.site_revision }}",
            self.workflow,
        )
        self.assertIn(
            "composition_ref: ${{ needs.resolve.outputs.composition_head }}",
            self.workflow,
        )
        self.assertNotIn("composition_ref: composition", self.workflow)
        self.assertNotIn("policy_ref:", self.workflow)

    def test_lock_divergence_is_warning_but_candidate_failure_is_error(self) -> None:
        relation_block = self.workflow.split(
            'if [ "$RELATION" = "different" ]; then',
            maxsplit=1,
        )[1].split("\n          fi", maxsplit=1)[0]
        self.assertIn("::warning::Composition publication lock differs", relation_block)
        self.assertNotIn("exit 1", relation_block)

        failure_block = self.workflow.split(
            'if [ "$CANDIDATE_RESULT" != "success" ]; then',
            maxsplit=1,
        )[1].split("\n          fi", maxsplit=1)[0]
        self.assertIn("::error::Current Composition HEAD", failure_block)
        self.assertIn("exit 1", failure_block)


if __name__ == "__main__":
    unittest.main()
