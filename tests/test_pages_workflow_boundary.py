from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-pages.yml"
SOURCE_LOCK = ROOT / "publication-sources.json"
DEPLOYMENT_STATE = ROOT / "deployment-state.json"


class PagesWorkflowBoundaryTests(unittest.TestCase):
    def test_reusable_workflow_remains_non_deploying_and_browser_check_is_pr_only(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
        trigger_block = workflow.split("\npermissions:\n", maxsplit=1)[0]
        build_block, check_block = workflow.split("\n  check:\n", maxsplit=1)

        self.assertIn(
            "  pull_request:\n    branches:\n      - site",
            trigger_block,
        )
        self.assertIn("  workflow_call:", trigger_block)
        self.assertNotIn("\n  push:\n", trigger_block)
        self.assertIn("composition_ref:", workflow)
        self.assertNotIn("skill_ref:", workflow)
        self.assertNotIn("webapp_ref:", workflow)
        self.assertNotIn("source_ref:", workflow)
        self.assertIn("actions/upload-pages-artifact@", build_block)
        self.assertNotIn("actions/download-artifact@", build_block)
        self.assertNotIn("actions/configure-pages@", workflow)
        self.assertNotIn("actions/deploy-pages@", workflow)
        self.assertNotIn("pages: write", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertNotIn("\n  deploy:\n", workflow)

        self.assertIn("needs: build", check_block)
        self.assertIn("github.event_name == 'pull_request'", check_block)
        self.assertIn("inputs.site_ref == ''", check_block)
        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            check_block,
        )
        self.assertIn("actions/download-artifact@v5", check_block)
        self.assertIn("name: github-pages", check_block)

    def test_reusable_workflow_checks_out_only_locked_external_providers(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("publication-sources.json", workflow)
        self.assertIn("path: composition-source", workflow)
        self.assertIn("path: policy-source", workflow)
        self.assertNotIn("path: skill-source", workflow)
        self.assertNotIn("path: webapp-source", workflow)
        self.assertIn(
            "python site-source/scripts/prepare_repository_tree_publication.py",
            workflow,
        )
        self.assertIn("--publication site=site-publication", workflow)
        self.assertIn("--publication composition=composition-source", workflow)
        self.assertIn("--publication policy=policy-source", workflow)
        self.assertNotIn("--publication skill=", workflow)
        self.assertNotIn("--publication webapp=", workflow)
        self.assertNotIn("generate_skill_template_tree.py", workflow)
        self.assertNotIn("generate_webapp_template_tree.py", workflow)

        source_lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
        self.assertEqual(
            set(source_lock["publications"]),
            {"composition", "policy"},
        )

    def test_publication_resolver_runs_under_pinned_python(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")

        setup_position = workflow.index("- name: Set up Python")
        resolver_position = workflow.index("- name: Resolve publication source revisions")
        provider_checkout_position = workflow.index("- name: Check out composition publication")

        self.assertLess(setup_position, resolver_position)
        self.assertLess(resolver_position, provider_checkout_position)
        self.assertIn("python-version: '3.12'", workflow)
        self.assertIn(
            "python site-source/scripts/resolve_publication_sources.py",
            workflow,
        )

    def test_site_push_workflow_is_the_only_deployment_authority(self) -> None:
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
        self.assertIn("github.repository == 'TakashiSasaki/templates'", workflow)
        self.assertIn("github.event_name == 'push'", workflow)
        self.assertIn("github.ref == 'refs/heads/site'", workflow)
        self.assertNotIn("github.event.repository.default_branch", workflow)

        self.assertIn("TZ=Asia/Tokyo", workflow)
        self.assertIn("deployment_timestamp:", workflow)
        self.assertIn("needs: deployment_metadata", workflow)
        self.assertIn("needs: build", workflow)
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("name: github-pages", workflow)
        self.assertIn("actions/configure-pages@v6", workflow)
        self.assertIn("actions/deploy-pages@v5", workflow)
        self.assertIn("\n  deploy:\n", workflow)

        metadata = workflow.index("  deployment_metadata:")
        build = workflow.index("  build:")
        deploy = workflow.index("  deploy:")
        self.assertLess(metadata, build)
        self.assertLess(build, deploy)

    def test_machine_readable_deployment_state_is_bound_to_composition(self) -> None:
        state = json.loads(DEPLOYMENT_STATE.read_text(encoding="utf-8"))
        source_lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))

        self.assertEqual(1, state["schema_version"])
        self.assertEqual("active", state["status"])
        self.assertIn("composition", state["reason"])
        self.assertEqual(
            source_lock["publications"]["composition"]["revision"],
            state["locked_composition_revision"],
        )
        self.assertRegex(
            state["locked_composition_revision"],
            r"\A[0-9a-f]{40}\Z",
        )
        conditions = state["completed_conditions"]
        self.assertIsInstance(conditions, list)
        self.assertGreaterEqual(len(conditions), 4)
        self.assertTrue(all(isinstance(value, str) and value for value in conditions))


if __name__ == "__main__":
    unittest.main()
