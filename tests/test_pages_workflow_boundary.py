from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-pages.yml"
SOURCE_LOCK = ROOT / "publication-sources.json"


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

    def test_deployment_workflow_accepts_only_site_pushes(self) -> None:
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
        self.assertNotIn("source_ref: skill", workflow)
        self.assertNotIn("source_ref: main", workflow)
        self.assertIn("github.event_name == 'push'", workflow)
        self.assertIn("github.ref == 'refs/heads/site'", workflow)
        self.assertNotIn("github.event.repository.default_branch", workflow)
        self.assertIn("actions/configure-pages@", workflow)
        self.assertIn("actions/deploy-pages@", workflow)
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("name: github-pages", workflow)


if __name__ == "__main__":
    unittest.main()
