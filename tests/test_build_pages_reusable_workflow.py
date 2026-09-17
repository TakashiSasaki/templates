from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.resolve_site_checkout import resolve_checkout

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/site-producer.yml"


class BuildPagesReusableWorkflowTests(unittest.TestCase):
    def test_reusable_build_hashes_the_pinned_site_workflow_definition(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        site_checkout = (
            "- name: Check out site implementation\n"
            "        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7\n"
            "        with:\n"
            "          ref: ${{ inputs.site_ref }}"
        )
        workflow_checkout = (
            "- name: Check out executed build workflow definition\n"
            "        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7\n"
            "        with:\n"
            "          ref: ${{ github.workflow_sha }}\n"
            "          path: workflow-source"
        )

        self.assertIn(site_checkout, text)
        self.assertIn(workflow_checkout, text)
        self.assertIn("workflow-source/.github/workflows/site-producer.yml", text)
        self.assertIn("run: python3 site-source/scripts/site_build_artifact.py", text)

    def test_reusable_build_keeps_artifact_discovery_read_only(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("    permissions:\n      contents: read\n      actions: read", text)
        self.assertIn("persist-credentials: false", text)

    def test_reusable_build_passes_resolved_checkout_sha_to_preflight(self):
        text = WORKFLOW.read_text()
        self.assertIn('python3 site-source/scripts/resolve_site_checkout.py', text)
        self.assertIn('ref: ${{ inputs.site_ref }}', text)
        self.assertIn('--lock site-source/integration-source.json', text)
        self.assertIn('scripts/render_publication_bundle.py', text)
        self.assertNotIn('composition_ref', text)
        self.assertNotIn('policy_ref', text)

    def test_commit_branch_tag_and_default_refs_bind_to_checked_out_head(self) -> None:
        for site_ref in ("full-sha", "branch", "tag", "default"):
            with self.subTest(site_ref=site_ref), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory) / "site-source"
                subprocess.run(["git", "init", "-b", "site", str(repository)], check=True)
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repository),
                        "config",
                        "user.email",
                        "site@example.invalid",
                    ],
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", str(repository), "config", "user.name", "Site Test"],
                    check=True,
                )
                (repository / "README.md").write_text("site\n", encoding="utf-8")
                subprocess.run(["git", "-C", str(repository), "add", "README.md"], check=True)
                subprocess.run(
                    ["git", "-C", str(repository), "commit", "-m", "site"], check=True
                )
                expected = subprocess.check_output(
                    ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
                ).strip()
                subprocess.run(
                    ["git", "-C", str(repository), "branch", "candidate", expected], check=True
                )
                subprocess.run(
                    ["git", "-C", str(repository), "tag", "candidate-tag", expected],
                    check=True,
                )

                target = {
                    "full-sha": expected,
                    "branch": "candidate",
                    "tag": "candidate-tag",
                    "default": "site",
                }[site_ref]
                subprocess.run(
                    ["git", "-C", str(repository), "checkout", "--detach", target],
                    check=True,
                    capture_output=True,
                )
                self.assertEqual(resolve_checkout(repository), expected)

    def test_reusable_site_ref_default_remains_site_branch(self):
        import yaml
        inputs=yaml.safe_load(WORKFLOW.read_text())[True]['workflow_call']['inputs']
        self.assertEqual(inputs['site_ref']['default'], '')
        self.assertNotIn('composition_ref', inputs)
        self.assertNotIn('policy_ref', inputs)

if __name__ == "__main__":
    unittest.main()
