from __future__ import annotations

import importlib.util
import os
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
        "release_candidate_hardening_test", CANDIDATE_SOURCE
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


class ReleaseCandidateHardeningTests(unittest.TestCase):
    def git_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        for name in tuple(environment):
            if name.startswith("GIT_"):
                del environment[name]
        environment.update(
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_AUTHOR_NAME": "Candidate hardening acceptance",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                "GIT_COMMITTER_NAME": "Candidate hardening acceptance",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            }
        )
        return environment

    def run_git(self, root: Path, *arguments: str) -> str:
        completed = subprocess.run(
            [
                "git",
                "-c",
                "core.autocrlf=false",
                "-c",
                "maintenance.auto=false",
                "-c",
                "gc.auto=0",
                "-C",
                str(root),
                *arguments,
            ],
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

    def create_repository(self, root: Path) -> str:
        (root / "tracked.txt").write_text("candidate\n", encoding="utf-8")
        self.run_git(root, "init", "--quiet")
        self.run_git(root, "add", "tracked.txt")
        self.run_git(root, "commit", "--quiet", "--message", "candidate")
        revision = self.run_git(root, "rev-parse", "--verify", "HEAD^{commit}")
        self.assertRegex(revision, r"^[0-9a-f]{40}$")
        return revision

    def test_output_path_rejects_unsafe_raw_segments_and_portable_forms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for relative in (
                ".",
                "..",
                "sub/..",
                "sub/.",
                "sub//file",
                "../outside",
                "sub\\..\\outside",
                "C:/outside",
            ):
                with self.subTest(relative=relative):
                    with self.assertRaisesRegex(
                        candidate.CandidateError,
                        "unsafe repository-relative path",
                    ):
                        candidate.ensure_output_path(root, relative)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_resolve_working_directory_rejects_symlink_components(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real = root / "real"
            real.mkdir()
            link = root / "linked"
            try:
                os.symlink(real, link, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"cannot create directory symlink: {exc}")
            with self.assertRaisesRegex(
                candidate.CandidateError,
                "release working directory crosses a symlink",
            ):
                candidate.resolve_working_directory(root, "linked")

    def test_staged_changes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            revision = self.create_repository(root)
            (root / "tracked.txt").write_text("staged drift\n", encoding="utf-8")
            self.run_git(root, "add", "tracked.txt")
            with self.assertRaisesRegex(
                candidate.CandidateError,
                "repository has staged changes",
            ):
                candidate.verify_candidate(root, revision)

    def test_replacement_refs_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            revision = self.create_repository(root)
            tree = self.run_git(root, "rev-parse", "HEAD^{tree}")
            replacement = self.run_git(
                root,
                "commit-tree",
                tree,
                "-m",
                "replacement candidate",
            )
            self.run_git(root, "replace", revision, replacement)
            with self.assertRaisesRegex(
                candidate.CandidateError,
                "Git replacement objects are not permitted",
            ):
                candidate.verify_candidate(root, revision)


if __name__ == "__main__":
    unittest.main()
