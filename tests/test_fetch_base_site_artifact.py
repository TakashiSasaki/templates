from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.fetch_base_site_artifact import (
    ArtifactError,
    candidate_runs,
    read_expected_inputs,
    select_artifact,
)
from scripts.site_build_artifact import identity_key


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "TakashiSasaki/templates"
BASE = "1" * 40


class BaseArtifactSelectionTests(unittest.TestCase):
    def test_direct_script_entrypoint_loads(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/fetch_base_site_artifact.py", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("PR base revision", result.stdout)

    def test_candidate_runs_are_base_bound_and_newest_first(self) -> None:
        def run(run_id: int, number: int, *, head: str = BASE, event: str = "pull_request", repo: str = REPOSITORY):
            return {
                "id": run_id,
                "path": ".github/workflows/build-pages.yml",
                "head_sha": head,
                "event": event,
                "head_repository": {"full_name": repo},
                "run_number": number,
                "run_attempt": 1,
            }

        runs = [
            run(10, 10),
            run(20, 20),
            run(30, 30, head="2" * 40),
            run(40, 40, event="push"),
            run(50, 50, repo="someone/fork"),
            run(60, 60),
        ]
        selected = candidate_runs(runs, repository=REPOSITORY, base_sha=BASE, current_run=60)
        self.assertEqual([20, 10], [entry["id"] for entry in selected])

    def test_select_artifact_requires_successful_unique_base_binding(self) -> None:
        run = {"id": 7}
        jobs = [{"name": "build / build", "status": "completed", "conclusion": "success"}]
        artifacts = [{
            "id": 11,
            "name": "github-pages",
            "expired": False,
            "digest": "sha256:" + "a" * 64,
            "workflow_run": {"id": 7, "head_sha": BASE},
        }]
        self.assertEqual(11, select_artifact(run, jobs, artifacts, base_sha=BASE)["id"])
        corrupted = [{**artifacts[0], "workflow_run": {"id": 7, "head_sha": "2" * 40}}]
        with self.assertRaises(ArtifactError):
            select_artifact(run, jobs, corrupted, base_sha=BASE)
        self.assertIsNone(select_artifact(run, [{**jobs[0], "conclusion": "failure"}], artifacts, base_sha=BASE))

    def test_manifest_reader_binds_repository_and_base_sha(self) -> None:
        inputs = {
            "schema_version": 1,
            "repository": REPOSITORY,
            "site": BASE,
            "composition": "3" * 40,
            "policy": "4" * 40,
            "workflow_sha256": "5" * 64,
            "staging": "",
            "staging_ids": "",
            "deployment_timestamp": "",
            "public_url": "https://templates.moukaeritai.work/",
            "runtime": "3.12|Linux|X64|ubuntu24|test",
            "qualification_suite": "integration-tests-with-core",
        }
        manifest = {"inputs": inputs, "identity": identity_key(inputs)}
        with tempfile.TemporaryDirectory() as tempdir:
            archive = Path(tempdir) / "pages.zip"
            tar_bytes = io.BytesIO()
            with tarfile.open(fileobj=tar_bytes, mode="w") as tar:
                payload = json.dumps(manifest).encode()
                info = tarfile.TarInfo("ci-build-inputs.json")
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("artifact.tar", tar_bytes.getvalue())
            digest = "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest()
            self.assertEqual(
                inputs,
                read_expected_inputs(archive, digest=digest, repository=REPOSITORY, base_sha=BASE),
            )
            with self.assertRaises(ArtifactError):
                read_expected_inputs(archive, digest=digest, repository=REPOSITORY, base_sha="9" * 40)


if __name__ == "__main__":
    unittest.main()
