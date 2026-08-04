from __future__ import annotations

import os
import py_compile
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from generated_release_evidence_producer_fixture import (  # noqa: E402
    _install_release_evidence_producer,
)
from test_generated_repository_conformance import (  # noqa: E402
    _generated_environment,
    _generated_repository,
    _is_template_maintainer_source,
    _load_json,
    _run_generated_python,
    _write_json,
)

_GIT_CONFIG_OVERRIDES = (
    "-c",
    "maintenance.auto=false",
    "-c",
    "gc.auto=0",
)


def _git_environment() -> dict[str, str]:
    environment = _generated_environment()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            del environment[name]
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_LITERAL_PATHSPECS": "1",
            "GIT_AUTHOR_NAME": "Webapp conformance fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_AUTHOR_DATE": "2026-08-04T00:00:00+00:00",
            "GIT_COMMITTER_NAME": "Webapp conformance fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_DATE": "2026-08-04T00:00:00+00:00",
        }
    )
    return environment


def _run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *_GIT_CONFIG_OVERRIDES, "-C", str(root), *arguments],
        cwd=root,
        env=_git_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(arguments)} failed\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _run_git_with_worktree(
    root: Path,
    worktree: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [
            "git",
            *_GIT_CONFIG_OVERRIDES,
            "--git-dir",
            str(root / ".git"),
            "--work-tree",
            str(worktree),
            *arguments,
        ],
        cwd=root,
        env=_git_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(arguments)} failed\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _commit_generated_repository(root: Path) -> str:
    _run_git(root, "init", "--quiet")
    _run_git(root, "add", "--all", "--force")
    _run_git(
        root,
        "commit",
        "--quiet",
        "--message",
        "Capture generated repository fixture",
    )
    revision = _run_git(root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    if len(revision) != 40:
        raise AssertionError(f"unexpected generated revision: {revision!r}")
    return revision


@unittest.skipUnless(
    _is_template_maintainer_source(),
    "template-maintainer-only generated release evidence production suite",
)
class GeneratedReleaseEvidenceProductionTests(unittest.TestCase):
    def run_producer(self, root: Path, revision: str):
        return _run_generated_python(
            root,
            "-I",
            "product/produce_release_evidence.py",
            "--revision",
            revision,
        )

    def assert_release_validates(self, root: Path, revision: str) -> None:
        for command in (
            (
                "scripts/validate_release_evidence.py",
                "--expected-revision",
                revision,
            ),
            (
                "-m",
                "scripts.validate_release_evidence",
                "--expected-revision",
                revision,
            ),
        ):
            with self.subTest(command=command):
                result = _run_generated_python(root, *command)
                self.assertEqual(
                    0,
                    result.returncode,
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
                )

    def test_reviewed_runner_produces_release_evidence_from_actual_execution(
        self,
    ) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            revision = _commit_generated_repository(root)

            result = self.run_producer(root, revision)

            self.assertEqual(
                0,
                result.returncode,
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
            self.assertIn(
                "generated release evidence: approved",
                result.stdout,
            )

            run = _load_json(root / "product/release-run.json")
            release = _load_json(root / "contracts/release-evidence.json")
            implementation = _load_json(
                root / "contracts/implementation-evidence.json"
            )

            self.assertEqual(revision, run["revision"])
            self.assertEqual(revision, run["revisionBinding"]["verifiedHead"])
            self.assertEqual("clean", run["revisionBinding"]["worktree"])
            self.assertEqual(
                "python product/prove_conformance.py",
                run["command"]["authoritativeCommand"],
            )
            self.assertEqual(
                [sys.executable, "-I", "product/prove_conformance.py"],
                run["command"]["executionArgv"],
            )
            self.assertEqual(0, run["command"]["exitCode"])
            self.assertIn(
                "generated repository proof: 52 checks passed",
                run["command"]["stdout"],
            )
            self.assertEqual("passed", run["command"]["status"])
            self.assertEqual("passed", run["gate"]["status"])
            self.assertEqual("approved", run["decision"]["status"])

            self.assertEqual("product", release["mode"])
            self.assertEqual(revision, release["subject"]["revision"])
            self.assertEqual(
                implementation["commands"][0]["id"],
                release["commandResults"][0]["commandId"],
            )
            self.assertEqual(
                run["command"]["startedAt"],
                release["commandResults"][0]["startedAt"],
            )
            self.assertEqual(
                run["command"]["completedAt"],
                release["commandResults"][0]["completedAt"],
            )
            self.assertEqual("passed", release["commandResults"][0]["status"])
            self.assertEqual(0, release["commandResults"][0]["exitCode"])
            self.assertEqual("passed", release["gateResults"][0]["status"])
            self.assertEqual("approved", release["decision"]["status"])

            self.assert_release_validates(root, revision)

        self.assertEqual(
            "template",
            _load_json(ROOT / "contracts/release-evidence.json")["mode"],
        )
        self.assertFalse((ROOT / "product").exists())

    def test_failed_reviewed_command_cannot_produce_approved_release(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            inventory_path = root / "product/conformance-targets.json"
            inventory = _load_json(inventory_path)
            first_target = next(iter(inventory["targets"].values()))
            first_target["positive"] = False
            _write_json(inventory_path, inventory)
            revision = _commit_generated_repository(root)

            result = self.run_producer(root, revision)

            self.assertEqual(1, result.returncode)
            self.assertIn(
                "generated release evidence: rejected",
                result.stderr,
            )

            run = _load_json(root / "product/release-run.json")
            release = _load_json(root / "contracts/release-evidence.json")
            self.assertEqual(revision, run["revisionBinding"]["verifiedHead"])
            self.assertEqual("clean", run["revisionBinding"]["worktree"])
            self.assertEqual("failed", run["command"]["status"])
            self.assertNotEqual(0, run["command"]["exitCode"])
            self.assertEqual("failed", run["gate"]["status"])
            self.assertEqual("rejected", run["decision"]["status"])
            self.assertEqual("failed", release["commandResults"][0]["status"])
            self.assertNotEqual(0, release["commandResults"][0]["exitCode"])
            self.assertEqual("failed", release["gateResults"][0]["status"])
            self.assertEqual("rejected", release["decision"]["status"])
            self.assertNotEqual("approved", release["decision"]["status"])

            validation = _run_generated_python(
                root,
                "scripts/validate_release_evidence.py",
                "--expected-revision",
                revision,
            )
            self.assertEqual(1, validation.returncode)
            self.assertIn("status must be passed", validation.stderr)
            self.assertIn("release status must be approved", validation.stderr)

    def test_runner_rejects_authoritative_command_drift_before_execution(
        self,
    ) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            implementation_path = root / "contracts/implementation-evidence.json"
            implementation = _load_json(implementation_path)
            implementation["commands"][0][
                "command"
            ] = "python -I product/prove_conformance.py"
            _write_json(implementation_path, implementation)
            revision = _commit_generated_repository(root)

            result = self.run_producer(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn(
                "authoritative command registration changed",
                result.stderr,
            )
            self.assertFalse((root / "product/release-run.json").exists())
            self.assertEqual(
                "template",
                _load_json(root / "contracts/release-evidence.json")["mode"],
            )

    def test_runner_rejects_revision_that_does_not_match_generated_tree(
        self,
    ) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            revision = _commit_generated_repository(root)
            mismatched_revision = "f" * 40
            self.assertNotEqual(revision, mismatched_revision)

            result = self.run_producer(root, mismatched_revision)

            self.assertEqual(2, result.returncode)
            self.assertIn(
                "revision does not match generated repository HEAD",
                result.stderr,
            )
            self.assertFalse((root / "product/release-run.json").exists())
            self.assertEqual(
                "template",
                _load_json(root / "contracts/release-evidence.json")["mode"],
            )

    def test_runner_rejects_uncommitted_generated_tree_changes(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            revision = _commit_generated_repository(root)
            inventory_path = root / "product/conformance-targets.json"
            inventory = _load_json(inventory_path)
            first_target = next(iter(inventory["targets"].values()))
            first_target["positive"] = False
            _write_json(inventory_path, inventory)

            result = self.run_producer(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn(
                "generated repository has uncommitted changes",
                result.stderr,
            )
            self.assertFalse((root / "product/release-run.json").exists())
            self.assertEqual(
                "template",
                _load_json(root / "contracts/release-evidence.json")["mode"],
            )

    def test_runner_rejects_ignored_executable_inputs(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            revision = _commit_generated_repository(root)
            cache = root / "product/__pycache__"
            cache.mkdir()
            cache_tag = sys.implementation.cache_tag or "python"
            ignored_bytecode = cache / f"prove_conformance.{cache_tag}.pyc"
            ignored_bytecode.write_bytes(b"revision-external-bytecode")

            status = _run_git(
                root,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            )
            self.assertEqual("", status.stdout)

            result = self.run_producer(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn(
                "generated repository has ignored uncommitted files",
                result.stderr,
            )
            self.assertIn(
                ignored_bytecode.relative_to(root).as_posix(),
                result.stderr,
            )
            self.assertFalse((root / "product/release-run.json").exists())
            self.assertEqual(
                "template",
                _load_json(root / "contracts/release-evidence.json")["mode"],
            )

    def test_producer_requires_isolation_before_repository_imports(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            revision = _commit_generated_repository(root)
            sentinel = root / "product/preflight-import-executed"
            malicious_source = root / "malicious_argparse.py"
            malicious_source.write_text(
                "from pathlib import Path\n"
                f"Path({str(sentinel)!r}).write_text('executed', encoding='utf-8')\n"
                "raise SystemExit(0)\n",
                encoding="utf-8",
            )
            ignored_bytecode = root / "product/argparse.pyc"
            py_compile.compile(
                str(malicious_source),
                cfile=str(ignored_bytecode),
                doraise=True,
            )
            malicious_source.unlink()

            result = _run_generated_python(
                root,
                "product/produce_release_evidence.py",
                "--revision",
                revision,
            )

            self.assertEqual(2, result.returncode)
            self.assertIn(
                "producer requires Python isolated mode (-I)",
                result.stderr,
            )
            self.assertFalse(sentinel.exists())
            self.assertFalse((root / "product/release-run.json").exists())
            self.assertEqual(
                "template",
                _load_json(root / "contracts/release-evidence.json")["mode"],
            )

    def test_runner_rejects_redirected_git_worktree(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            revision = _commit_generated_repository(root)
            alternate = root.parent / "alternate-worktree"
            alternate.mkdir()
            _run_git_with_worktree(
                root,
                alternate,
                "checkout",
                "--quiet",
                "--force",
                revision,
            )
            _run_git(root, "config", "core.worktree", str(alternate))
            proof_path = root / "product/prove_conformance.py"
            proof_path.write_text(
                "print('generated repository proof: 52 checks passed')\n",
                encoding="utf-8",
            )

            redirected_status = _run_git(
                root,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            )
            self.assertEqual("", redirected_status.stdout)

            result = self.run_producer(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn(
                "Git resolved worktree does not match generated repository root",
                result.stderr,
            )
            self.assertFalse((root / "product/release-run.json").exists())
            self.assertEqual(
                "template",
                _load_json(root / "contracts/release-evidence.json")["mode"],
            )


class GeneratedReleaseEvidenceProductionScopeTests(unittest.TestCase):
    def test_generated_release_production_suite_is_template_maintainer_only(
        self,
    ) -> None:
        source_is_template = _is_template_maintainer_source()
        suite_is_skipped = bool(
            getattr(
                GeneratedReleaseEvidenceProductionTests,
                "__unittest_skip__",
                False,
            )
        )
        self.assertEqual(not source_is_template, suite_is_skipped)
        if suite_is_skipped:
            self.assertEqual(
                "template-maintainer-only generated release evidence production suite",
                getattr(
                    GeneratedReleaseEvidenceProductionTests,
                    "__unittest_skip_why__",
                ),
            )


if __name__ == "__main__":
    unittest.main()
