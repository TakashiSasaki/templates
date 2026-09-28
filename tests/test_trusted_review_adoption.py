from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/trusted-review-bootstrap.yml"
ACTION = ROOT / ".github/actions/trusted-review-freeze-role/action.yml"
ADOPTION = ROOT / "trusted-review-adoption.json"
SOURCE_REVISION = "71fad184a072c9335af793ac1efb7e6332c449b0"


class TrustedReviewAdoptionTests(unittest.TestCase):
    def test_adopted_projection_matches_exact_policy_objects(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/verify_trusted_review_adoption.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(SOURCE_REVISION, result.stdout)
        self.assertIn("files=11", result.stdout)

    def test_workflow_is_dispatch_only_site_default_branch_trust_root(self) -> None:
        workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(
            workflow["jobs"]["bootstrap"]["if"],
            "github.repository_id == '1315875002' && github.ref == 'refs/heads/site'",
        )
        self.assertEqual(
            workflow["jobs"]["bootstrap"]["permissions"],
            {
                "contents": "read",
                "pull-requests": "read",
                "id-token": "write",
                "attestations": "write",
                "packages": "write",
            },
        )
        checkout = workflow["jobs"]["bootstrap"]["steps"][0]["with"]
        self.assertEqual(checkout["ref"], "${{ github.workflow_sha }}")
        self.assertEqual(checkout["persist-credentials"], "false")
        self.assertEqual(checkout["fetch-depth"], "1")
        source = WORKFLOW.read_text(encoding="utf-8")
        for forbidden in ("pull_request_target", "pull_request:", "pull-requests: write"):
            self.assertNotIn(forbidden, source)
        self.assertIn("ghcr.io/takashisasaki/templates/trusted-review-authority", source)
        self.assertIn("github.workflow_sha", source)
        self.assertIn("TRUSTED_REVIEW_ACTOR_ID", source)
        self.assertEqual(workflow["permissions"], {"contents": "read"})

    def test_actions_are_pinned_and_target_head_is_data_only(self) -> None:
        sources = [WORKFLOW.read_text(encoding="utf-8"), ACTION.read_text(encoding="utf-8")]
        uses = re.findall(r"(?m)^\s*uses:\s*([^\s]+)", "\n".join(sources))
        external = [reference for reference in uses if not reference.startswith("./")]
        self.assertTrue(external)
        self.assertTrue(all(re.search(r"@[0-9a-f]{40}(?:\s|$)", ref) for ref in external))
        local = [ref for ref in uses if ref.startswith("./")]
        self.assertEqual(set(local), {"./.github/actions/trusted-review-freeze-role"})
        self.assertEqual(len(local), 4)
        self.assertEqual(WORKFLOW.read_text(encoding="utf-8").count("actions/checkout@"), 1)
        provider = (ROOT / "scripts/trusted_review_freeze_provider.py").read_text(encoding="utf-8")
        self.assertIn('DATA_ONLY_CONTAINER_COMMAND = "/__trusted_review_data_only__"', provider)
        tree = ast.parse(provider)
        functions = {
            item.name: item
            for item in ast.walk(tree)
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for name in ("hydrate_handoff", "_protect_aggregate", "_protect_role"):
            self.assertTrue(any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_create_data_only_container"
                for node in ast.walk(functions[name])
            ), name)

    def test_observation_binds_policy_base_and_independent_dispatch_actor(self) -> None:
        observer = (ROOT / "scripts/trusted_review_actions.py").read_text(encoding="utf-8")
        self.assertIn('POLICY_BASE_REF = "policy"', observer)
        self.assertIn("base_ref != POLICY_BASE_REF", observer)
        self.assertIn("author_id", observer)
        self.assertIn("actor_id", observer)
        self.assertIn("run_attempt", observer)
        self.assertIn("workflow_ref != WORKFLOW_REF", observer)
        self.assertIn("workflow_sha", observer)
        self.assertIn("base_ref != POLICY_BASE_REF", observer)
        self.assertIn("base_tree", observer)
        self.assertIn("head_tree", observer)
        self.assertIn("pull-request author cannot dispatch", observer)
        self.assertIn('run_attempt_raw != "1"', observer)
        manifest = json.loads(ADOPTION.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source"]["revision"], SOURCE_REVISION)
        self.assertEqual(manifest["source"]["tree"], "78d19c3683d9b4cb2d15deaec021021b3b43014d")
        self.assertEqual(len(manifest["adopted_files"]), 11)
        self.assertIn(".agent-policy.lock", [item["path"] for item in manifest["runtime_inputs"]])
        self.assertIn(".review-authority/review-policy.md", [item["path"] for item in manifest["runtime_inputs"]])

    def test_schemas_parse_and_runtime_modules_compile(self) -> None:
        for path in sorted((ROOT / "schemas").glob("trusted-review-*.schema.json")):
            json.loads(path.read_text(encoding="utf-8"))
        modules = [
            "scripts/prepare_trusted_review_handoff.py",
            "scripts/trusted_review_actions.py",
            "scripts/trusted_review_freeze.py",
            "scripts/trusted_review_freeze_provider.py",
        ]
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", *modules],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
