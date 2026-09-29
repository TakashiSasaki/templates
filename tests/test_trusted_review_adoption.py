from __future__ import annotations

import ast
import hashlib
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
SOURCE_REVISION = "99bb2f7f68ff4af3e72cd4cd583f6bcc0908ea53"


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
        self.assertIn("files=17", result.stdout)
        self.assertIn("exact=16 transformed=1 closure=38", result.stdout)
        self.assertIn(
            "build_closure_sha256=1ecbbab6b11197dc798e1da19ca1bbecfbec879e0102835f60e84832ef8b6ca4",
            result.stdout,
        )

    def test_workflow_is_dispatch_only_site_default_branch_trust_root(self) -> None:
        workflow = yaml.load(
            WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
        )
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
        self.assertEqual(
            workflow["jobs"]["bootstrap"]["env"]["TRUSTED_REVIEW_PROTECTED_ROOT"],
            "${{ runner.temp }}/trusted-review/role-protected",
        )
        self.assertEqual(
            workflow["jobs"]["stage-build"]["permissions"], {"contents": "read"}
        )
        self.assertEqual(
            workflow["jobs"]["stage-build"]["steps"][0]["with"]["ref"],
            "${{ github.workflow_sha }}",
        )
        self.assertEqual(
            workflow["jobs"]["stage-build"]["steps"][2]["with"]["ref"],
            "${{ steps.target.outputs.base_sha }}",
        )
        self.assertIn(
            "policy-source/skills/agent-policy/scripts/prepare_runtime_wheel.py",
            workflow["jobs"]["stage-build"]["steps"][3]["run"],
        )
        manifest = json.loads(ADOPTION.read_text(encoding="utf-8"))
        self.assertEqual(manifest["adoption_procedure"]["version"], 3)
        self.assertEqual(manifest["source"]["revision"], SOURCE_REVISION)
        self.assertEqual(
            manifest["source"]["tree"], "96f85ca44c61de583a658bb41bd9f2b3d2c5549f"
        )
        self.assertEqual(manifest["source"]["reviewed_prs"], [1090, 1095])
        self.assertEqual(len(manifest["adopted_files"]), 17)
        self.assertEqual(len(manifest["runtime_inputs"]), 38)
        self.assertEqual(
            manifest["adopted_files"][0]["transformation"]["id"],
            "site.trusted-review-add-role-protected-root-env",
        )
        checkout = workflow["jobs"]["bootstrap"]["steps"][0]["with"]
        self.assertEqual(checkout["ref"], "${{ github.workflow_sha }}")
        self.assertEqual(checkout["persist-credentials"], "false")
        self.assertEqual(checkout["fetch-depth"], "1")
        source = WORKFLOW.read_text(encoding="utf-8")
        for forbidden in (
            "pull_request_target",
            "pull_request:",
            "pull-requests: write",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn(
            "ghcr.io/takashisasaki/templates/trusted-review-authority", source
        )
        self.assertIn("github.workflow_sha", source)
        self.assertIn("TRUSTED_REVIEW_ACTOR_ID", source)
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(
            workflow["jobs"]["bootstrap"]["env"]["AGENT_POLICY_REQUIRE_PREBUILT_BUILD"],
            "1",
        )

    def test_pep517_build_closure_and_runtime_identity_are_exact(self) -> None:
        manifest = json.loads(ADOPTION.read_text(encoding="utf-8"))
        runtime_paths = {item["path"] for item in manifest["runtime_inputs"]}
        expected_paths = {
            "skills/agent-policy/build-closure.json",
            "skills/agent-policy/scripts/build_closure.py",
            "skills/agent-policy/scripts/prepare_runtime_wheel.py",
            "skills/agent-policy/scripts/runtime.py",
            "skills/agent-policy/scripts/runtime_image.py",
            "skills/agent-policy/runtime-manifest.json",
        }
        self.assertTrue(expected_paths <= runtime_paths)
        closure_path = ROOT / "skills/agent-policy/build-closure.json"
        closure_bytes = closure_path.read_bytes()
        self.assertEqual(
            hashlib.sha256(closure_bytes).hexdigest(),
            "1ecbbab6b11197dc798e1da19ca1bbecfbec879e0102835f60e84832ef8b6ca4",
        )
        closure = json.loads(closure_bytes)
        artifacts = {item["name"]: item for item in closure["artifacts"]}
        self.assertEqual(artifacts["pip"]["version"], "26.2.1")
        self.assertEqual(
            artifacts["pip"]["sha256"],
            "71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e",
        )
        self.assertEqual(artifacts["hatchling"]["version"], "1.31.0")
        self.assertEqual(
            artifacts["hatchling"]["sha256"],
            "aac80bec8b6fe35e8480f1c335be8910fa210a0e6f735a139be205dadcacb544",
        )
        self.assertEqual(len(artifacts), 6)
        builder = (
            ROOT / "skills/agent-policy/scripts/prepare_runtime_wheel.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"--no-index"', builder)
        self.assertIn('"--no-build-isolation"', builder)
        runtime = (ROOT / "skills/agent-policy/scripts/runtime.py").read_text(
            encoding="utf-8"
        )
        runtime_image = (
            ROOT / "skills/agent-policy/scripts/runtime_image.py"
        ).read_text(encoding="utf-8")
        for field in (
            "build_closure_sha256",
            "backend_artifact_sha256",
            "build_frontend_artifact_sha256",
            "builder_contract",
        ):
            self.assertIn(field, runtime)
            self.assertIn(field, runtime_image)

    def test_actions_are_pinned_and_target_head_is_data_only(self) -> None:
        sources = [
            WORKFLOW.read_text(encoding="utf-8"),
            ACTION.read_text(encoding="utf-8"),
        ]
        uses = re.findall(r"(?m)^\s*uses:\s*([^\s]+)", "\n".join(sources))
        external = [reference for reference in uses if not reference.startswith("./")]
        self.assertTrue(external)
        self.assertTrue(
            all(re.search(r"@[0-9a-f]{40}(?:\s|$)", ref) for ref in external)
        )
        local = [ref for ref in uses if ref.startswith("./")]
        self.assertEqual(set(local), {"./.github/actions/trusted-review-freeze-role"})
        self.assertEqual(len(local), 4)
        self.assertEqual(
            WORKFLOW.read_text(encoding="utf-8").count("actions/checkout@"), 3
        )
        provider = (ROOT / "scripts/trusted_review_freeze_provider.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'DATA_ONLY_CONTAINER_COMMAND = "/__trusted_review_data_only__"', provider
        )
        tree = ast.parse(provider)
        functions = {
            item.name: item
            for item in ast.walk(tree)
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for name in ("hydrate_handoff", "_protect_aggregate", "_protect_role"):
            self.assertTrue(
                any(
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_create_data_only_container"
                    for node in ast.walk(functions[name])
                ),
                name,
            )

    def test_observation_binds_policy_base_and_independent_dispatch_actor(self) -> None:
        observer = (ROOT / "scripts/trusted_review_actions.py").read_text(
            encoding="utf-8"
        )
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
        self.assertEqual(
            manifest["source"]["tree"], "96f85ca44c61de583a658bb41bd9f2b3d2c5549f"
        )
        self.assertEqual(len(manifest["adopted_files"]), 17)
        self.assertEqual(len(manifest["runtime_inputs"]), 38)
        self.assertIn(
            ".agent-policy.lock", [item["path"] for item in manifest["runtime_inputs"]]
        )
        self.assertIn(
            ".review-authority/review-policy.md",
            [item["path"] for item in manifest["runtime_inputs"]],
        )

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
