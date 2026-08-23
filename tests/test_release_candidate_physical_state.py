from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SOURCE = (
    ROOT
    / "components/lifecycle.release-execution/files/.template-composition/release/candidate.py"
)


def load_candidate_module():
    spec = importlib.util.spec_from_file_location(
        "release_candidate_physical_state_test", CANDIDATE_SOURCE
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load candidate helper")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


candidate = load_candidate_module()


class ReleaseCandidatePhysicalStateTests(unittest.TestCase):
    def git_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        for name in tuple(environment):
            if name.startswith("GIT_"):
                del environment[name]
        environment.update(
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_AUTHOR_NAME": "Candidate physical-state acceptance",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                "GIT_COMMITTER_NAME": "Candidate physical-state acceptance",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            }
        )
        return environment

    def run_git(self, root: Path, *arguments: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            env=self.git_environment(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"git {' '.join(arguments)} failed\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        return completed.stdout.strip()

    def commit_repository(self, root: Path) -> str:
        self.run_git(root, "init", "--quiet")
        self.run_git(root, "add", "--all")
        self.run_git(root, "commit", "--quiet", "--message", "candidate")
        return self.run_git(root, "rev-parse", "--verify", "HEAD^{commit}")

    def test_deleted_tracked_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("candidate\n", encoding="utf-8")
            revision = self.commit_repository(root)
            tracked.unlink()
            with self.assertRaisesRegex(
                candidate.CandidateError,
                "raw tracked bytes differ",
            ):
                candidate.verify_candidate(root, revision)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_tracked_path_symlink_ancestor_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            root = workspace / "repo"
            root.mkdir()
            nested = root / "sub"
            nested.mkdir()
            (nested / "file.txt").write_text("candidate\n", encoding="utf-8")
            revision = self.commit_repository(root)

            outside = workspace / "outside"
            outside.mkdir()
            (outside / "file.txt").write_text("candidate\n", encoding="utf-8")
            shutil.rmtree(nested)
            try:
                os.symlink(outside, nested, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"cannot create directory symlink: {exc}")

            with self.assertRaisesRegex(
                candidate.CandidateError,
                "repository path crosses a symlink",
            ):
                candidate.verify_candidate(root, revision)


if __name__ == "__main__":
    unittest.main()
