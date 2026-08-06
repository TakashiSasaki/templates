from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-pages.yml"
SOURCE_LOCK = ROOT / "publication-sources.json"
DEPLOYMENT_STATE = ROOT / "deployment-state.json"
FINAL_WEBAPP_REVISION = "1671c5b503377b87d157aeaa714bdf7c43797dc9"
WEBAPP_INTEGRATION_REVISION = "552af87fb32e614072ac195e83514e47feaf5c01"
SITE_PRE_RESTORATION_REVISION = "f372805850848fb4fc05205ebb47d27e5e6b45f6"


class PagesWorkflowBoundaryTests(unittest.TestCase):
    def test_reusable_workflow_is_build_only(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
        trigger_block = workflow.split("\npermissions:\n", maxsplit=1)[0]

        self.assertIn(
            "  pull_request:\n    branches:\n      - site",
            trigger_block,
        )
        self.assertIn("  workflow_call:", trigger_block)
        self.assertNotIn("\n  push:\n", trigger_block)
        self.assertIn("Deprecated compatibility alias for skill_ref", workflow)
        self.assertIn("actions/upload-pages-artifact@", workflow)
        self.assertNotIn("actions/configure-pages@", workflow)
        self.assertNotIn("actions/deploy-pages@", workflow)
        self.assertNotIn("pages: write", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertNotIn("name: github-pages", workflow)
        self.assertNotIn("\n  deploy:\n", workflow)

    def test_reusable_workflow_checks_out_all_locked_publications(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("publication-sources.json", workflow)
        self.assertIn("path: skill-source", workflow)
        self.assertIn("path: policy-source", workflow)
        self.assertIn("path: webapp-source", workflow)
        self.assertIn(
            "python site-source/scripts/prepare_repository_tree_publication.py",
            workflow,
        )
        self.assertIn("--publication site=site-publication", workflow)
        self.assertIn("--publication skill=skill-source", workflow)
        self.assertIn("--publication policy=policy-source", workflow)
        self.assertIn("--publication webapp=webapp-source", workflow)
        self.assertNotIn("--publication site=site-source", workflow)
        self.assertNotIn("path: canonical-source", workflow)

        source_lock = SOURCE_LOCK.read_text(encoding="utf-8")
        self.assertIn('"skill"', source_lock)
        self.assertIn('"policy"', source_lock)
        self.assertIn('"webapp"', source_lock)

    def test_publication_resolver_runs_under_pinned_python(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")

        setup_position = workflow.index("- name: Set up Python")
        resolver_position = workflow.index("- name: Resolve publication source revisions")
        provider_checkout_position = workflow.index("- name: Check out skill publication")

        self.assertLess(setup_position, resolver_position)
        self.assertLess(resolver_position, provider_checkout_position)
        self.assertIn("python-version: '3.12'", workflow)
        self.assertIn(
            "python site-source/scripts/resolve_publication_sources.py",
            workflow,
        )

    def test_site_push_workflow_deploys_only_after_a_successful_build(self) -> None:
        workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        trigger_block = workflow.split("\npermissions:\n", maxsplit=1)[0]

        self.assertIn(
            "  push:\n    branches:\n      - site",
            trigger_block,
        )
        self.assertNotIn("pull_request:", trigger_block)
        self.assertNotIn("workflow_call:", trigger_block)
        self.assertNotIn("workflow_dispatch:", trigger_block)
        self.assertIn("uses: ./.github/workflows/build-pages.yml", workflow)
        self.assertIn("site_ref: ${{ github.sha }}", workflow)
        self.assertIn(
            "deployment_timestamp: "
            "${{ needs.deployment_metadata.outputs.deployment_timestamp }}",
            workflow,
        )
        self.assertIn("github.event_name == 'push'", workflow)
        self.assertIn("github.ref == 'refs/heads/site'", workflow)
        self.assertNotIn("github.event.repository.default_branch", workflow)
        self.assertIn("\n  deployment_metadata:\n", workflow)
        self.assertIn("\n  build:\n", workflow)
        self.assertIn("\n  deploy:\n", workflow)
        self.assertIn("needs: deployment_metadata", workflow)
        self.assertIn("needs: build", workflow)
        self.assertIn("actions/configure-pages@v6", workflow)
        self.assertIn("actions/deploy-pages@v5", workflow)
        self.assertEqual(1, workflow.count("pages: write"))
        self.assertEqual(1, workflow.count("id-token: write"))
        self.assertEqual(1, workflow.count("name: github-pages"))
        self.assertIn("url: ${{ steps.deployment.outputs.page_url }}", workflow)

    def test_machine_readable_deployment_state_is_active(self) -> None:
        state = json.loads(DEPLOYMENT_STATE.read_text(encoding="utf-8"))

        self.assertEqual(1, state["schema_version"])
        self.assertEqual("active", state["status"])
        self.assertIn("webapp", state["reason"])
        self.assertEqual(
            FINAL_WEBAPP_REVISION,
            state["restored_after"]["webapp_revision"],
        )
        self.assertEqual(
            WEBAPP_INTEGRATION_REVISION,
            state["restored_after"]["webapp_integration_revision"],
        )
        self.assertEqual(
            SITE_PRE_RESTORATION_REVISION,
            state["restored_after"]["site_pre_restoration_revision"],
        )
        self.assertEqual(
            {
                "trigger": "push to refs/heads/site",
                "build_workflow": ".github/workflows/build-pages.yml",
                "environment": "github-pages",
            },
            state["deployment_boundary"],
        )


if __name__ == "__main__":
    unittest.main()
